"""security and workflow integrity hardening

Revision ID: 0008_security_integrity
Revises: 0007_core_ops_completion
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_security_integrity"
down_revision = "0007_core_ops_completion"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.add_column("users", sa.Column("mfa_last_timestep", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint("uq_membership_one_lodge_per_user", "memberships", ["user_id"])
    op.add_column("memberships", sa.Column("previous_role_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_membership_previous_role", "memberships", "roles", ["previous_role_id"], ["id"], ondelete="SET NULL")
    op.add_column("tasks", sa.Column("proof_required", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("activities", sa.Column("requires_vehicle", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("transfers", sa.Column("delay_minutes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("transfers", sa.Column("delay_reason", sa.Text(), nullable=False, server_default=""))
    op.add_column("vehicles", sa.Column("fuel_level_percent", sa.Integer(), nullable=True))
    op.create_check_constraint("ck_vehicle_fuel_level", "vehicles", "fuel_level_percent IS NULL OR (fuel_level_percent >= 0 AND fuel_level_percent <= 100)")
    op.add_column("meal_services", sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_meal_department", "meal_services", "departments", ["department_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_meal_services_department", "meal_services", ["department_id"])
    op.create_index("ix_guests_lodge_created", "guests", ["lodge_id","created_at"])
    op.create_index("ix_stays_lodge_status_arrival", "stays", ["lodge_id","status","arrival_date"])
    op.add_column("lodges", sa.Column("protected_species", sa.Text(), nullable=False, server_default="rhino,black rhino,white rhino"))

    # Align room status vocabulary and keep a strict DB check.
    op.execute("ALTER TABLE units DROP CONSTRAINT IF EXISTS ck_unit_status")
    op.execute("UPDATE units SET status='available' WHERE status='vacant'")
    op.execute("UPDATE units SET status='cleaning' WHERE status='needs_cleaning'")
    op.execute("UPDATE units SET status='awaiting_inspection' WHERE status='inspection'")
    op.create_check_constraint("ck_unit_status", "units", "status in ('available','occupied','cleaning','awaiting_inspection','ready','maintenance','out_of_service')")
    op.alter_column("units", "status", server_default="available")

    # Half-open stay ranges permit same-day turnover and prevent concurrent double booking.
    op.execute("""ALTER TABLE stays ADD CONSTRAINT ex_stay_unit_overlap EXCLUDE USING gist
        (lodge_id WITH =, unit_id WITH =, daterange(arrival_date, departure_date, '[)') WITH &&)
        WHERE (status <> 'cancelled')""")
    op.execute("""ALTER TABLE activities ADD CONSTRAINT ex_activity_vehicle_overlap EXCLUDE USING gist
        (lodge_id WITH =, vehicle_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&)
        WHERE (vehicle_id IS NOT NULL AND status NOT IN ('completed','cancelled'))""")
    op.execute("""ALTER TABLE activities ADD CONSTRAINT ex_activity_guide_overlap EXCLUDE USING gist
        (lodge_id WITH =, guide_staff_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&)
        WHERE (guide_staff_id IS NOT NULL AND status NOT IN ('completed','cancelled'))""")
    op.execute("""ALTER TABLE transfers ADD CONSTRAINT ex_transfer_vehicle_overlap EXCLUDE USING gist
        (lodge_id WITH =, vehicle_id WITH =, tstzrange(scheduled_at, expected_end_at, '[)') WITH &&)
        WHERE (vehicle_id IS NOT NULL AND status NOT IN ('completed','cancelled'))""")
    op.execute("""ALTER TABLE transfers ADD CONSTRAINT ex_transfer_driver_overlap EXCLUDE USING gist
        (lodge_id WITH =, driver_staff_id WITH =, tstzrange(scheduled_at, expected_end_at, '[)') WITH &&)
        WHERE (driver_staff_id IS NOT NULL AND status NOT IN ('completed','cancelled'))""")

    # A guest cannot be linked to two overlapping active activities.
    op.execute("""
    CREATE OR REPLACE FUNCTION prevent_guest_activity_overlap() RETURNS trigger AS $$
    BEGIN
      IF EXISTS (
        SELECT 1 FROM activity_guests ag
        JOIN activities existing ON existing.id=ag.activity_id
        JOIN activities incoming ON incoming.id=NEW.activity_id
        WHERE ag.guest_id=NEW.guest_id AND ag.activity_id<>NEW.activity_id
          AND existing.lodge_id=NEW.lodge_id
          AND existing.status NOT IN ('completed','cancelled')
          AND incoming.status NOT IN ('completed','cancelled')
          AND tstzrange(existing.starts_at,existing.ends_at,'[)') && tstzrange(incoming.starts_at,incoming.ends_at,'[)')
      ) THEN RAISE EXCEPTION 'guest activity overlap' USING ERRCODE='23P01'; END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    CREATE TRIGGER trg_guest_activity_overlap BEFORE INSERT OR UPDATE ON activity_guests
      FOR EACH ROW EXECUTE FUNCTION prevent_guest_activity_overlap();
    """)

    # Append-only operational history and audit evidence.
    op.execute("""
    CREATE OR REPLACE FUNCTION deny_history_mutation() RETURNS trigger AS $$
    BEGIN RAISE EXCEPTION 'history is append-only' USING ERRCODE='42501'; END; $$ LANGUAGE plpgsql;
    CREATE TRIGGER trg_operational_events_append_only BEFORE UPDATE OR DELETE ON operational_events FOR EACH ROW EXECUTE FUNCTION deny_history_mutation();
    CREATE TRIGGER trg_audit_logs_append_only BEFORE UPDATE OR DELETE ON audit_logs FOR EACH ROW EXECUTE FUNCTION deny_history_mutation();
    DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='lodge_app') THEN
        EXECUTE 'REVOKE UPDATE, DELETE ON operational_events, audit_logs FROM lodge_app';
      END IF;
    END $$;
    """)

    perms = {
        "staff.hr.view": "View HR leave, credentials, training and roster data",
        "staff.contact.view": "View staff contact and employee-code fields",
        "wildlife.precise": "View precise coordinates for protected wildlife",
        "audit.view": "View the lodge-scoped audit log",
    }
    for key, desc in perms.items():
        op.execute(sa.text("INSERT INTO permissions(id,key,description) VALUES(gen_random_uuid(),:k,:d) ON CONFLICT(key) DO NOTHING").bindparams(k=key,d=desc))
    grants = {
        "lodge_admin": list(perms.keys()),
        "department_manager": ["staff.hr.view", "staff.contact.view", "wildlife.precise"],
        "ranger": ["wildlife.precise"],
        "finance": ["staff.contact.view", "maintenance.view"],
    }
    for role, keys in grants.items():
        for key in keys:
            op.execute(sa.text("INSERT INTO role_permissions(role_id,permission_id) SELECT r.id,p.id FROM roles r,permissions p WHERE r.key=:r AND p.key=:p ON CONFLICT DO NOTHING").bindparams(r=role,p=key))


def downgrade():
    op.execute("DELETE FROM role_permissions WHERE role_id=(SELECT id FROM roles WHERE key='finance') AND permission_id=(SELECT id FROM permissions WHERE key='maintenance.view')")
    for key in ["staff.hr.view", "staff.contact.view", "wildlife.precise", "audit.view"]:
        op.execute(sa.text("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE key=:p)").bindparams(p=key))
        op.execute(sa.text("DELETE FROM permissions WHERE key=:p").bindparams(p=key))
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_append_only ON audit_logs")
    op.execute("DROP TRIGGER IF EXISTS trg_operational_events_append_only ON operational_events")
    op.execute("DROP FUNCTION IF EXISTS deny_history_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_guest_activity_overlap ON activity_guests")
    op.execute("DROP FUNCTION IF EXISTS prevent_guest_activity_overlap()")
    for table, constraint in [
        ("transfers","ex_transfer_driver_overlap"),("transfers","ex_transfer_vehicle_overlap"),
        ("activities","ex_activity_guide_overlap"),("activities","ex_activity_vehicle_overlap"),
        ("stays","ex_stay_unit_overlap")]:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint}")
    op.execute("ALTER TABLE units DROP CONSTRAINT IF EXISTS ck_unit_status")
    op.execute("UPDATE units SET status='vacant' WHERE status='available'")
    op.execute("UPDATE units SET status='needs_cleaning' WHERE status='cleaning'")
    op.execute("UPDATE units SET status='inspection' WHERE status='awaiting_inspection'")
    op.create_check_constraint("ck_unit_status", "units", "status in ('vacant','occupied','needs_cleaning','cleaning','inspection','ready','maintenance','out_of_service')")
    op.alter_column("units", "status", server_default="vacant")
    op.drop_column("lodges", "protected_species")
    op.drop_index("ix_stays_lodge_status_arrival", table_name="stays")
    op.drop_index("ix_guests_lodge_created", table_name="guests")
    op.drop_index("ix_meal_services_department", table_name="meal_services")
    op.drop_constraint("fk_meal_department", "meal_services", type_="foreignkey")
    op.drop_column("meal_services", "department_id")
    op.drop_constraint("ck_vehicle_fuel_level", "vehicles", type_="check")
    op.drop_column("vehicles", "fuel_level_percent")
    op.drop_column("transfers", "delay_reason")
    op.drop_column("transfers", "delay_minutes")
    op.drop_column("activities", "requires_vehicle")
    op.drop_column("tasks", "proof_required")
    op.drop_constraint("fk_membership_previous_role", "memberships", type_="foreignkey")
    op.drop_constraint("uq_membership_one_lodge_per_user", "memberships", type_="unique")
    op.drop_column("memberships", "previous_role_id")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_count")
    op.drop_column("users", "mfa_last_timestep")

"""Separate guest identities, stay grants and guest-only database projections."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0027_guest_portal"
down_revision = "0026_offline_push"
branch_labels = depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("is_guest", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_check_constraint(
        "ck_user_guest_platform", "users", "NOT (is_guest AND is_super_admin)"
    )
    op.create_unique_constraint(
        "uq_stay_guest_lodge", "stays", ["id", "guest_id", "lodge_id"]
    )
    op.create_table(
        "guest_access",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column(
            "lodge_id",
            UUID(),
            sa.ForeignKey("lodges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "guest_id",
            UUID(),
            sa.ForeignKey("guests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "stay_id",
            UUID(),
            sa.ForeignKey("stays.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            UUID(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["stay_id", "guest_id", "lodge_id"],
            ["stays.id", "stays.guest_id", "stays.lodge_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("stay_id", "user_id", name="uq_guest_access_stay_user"),
        sa.UniqueConstraint("id", "lodge_id", "user_id", name="uq_guest_access_owner"),
    )
    op.create_index("ix_guest_access_lodge_id", "guest_access", ["lodge_id"])
    op.create_index("ix_guest_access_user_id", "guest_access", ["user_id"])
    op.create_table(
        "guest_portal_content",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column(
            "lodge_id",
            UUID(),
            sa.ForeignKey("lodges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column(
            "updated_by_user_id",
            UUID(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_guest_portal_content_lodge_id", "guest_portal_content", ["lodge_id"]
    )
    for table in ["guest_notices", "guest_ai_messages"]:
        columns = [
            sa.Column("id", UUID(), primary_key=True),
            sa.Column("access_id", UUID(), nullable=False),
            sa.Column(
                "lodge_id",
                UUID(),
                sa.ForeignKey("lodges.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                UUID(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["access_id", "lodge_id", "user_id"],
                ["guest_access.id", "guest_access.lodge_id", "guest_access.user_id"],
                ondelete="CASCADE",
            ),
        ]
        if table == "guest_notices":
            columns += [
                sa.Column("title", sa.String(160), nullable=False),
                sa.Column("body", sa.String(1000), nullable=False),
                sa.Column("dedupe_key", sa.String(160), nullable=False),
                sa.Column("read_at", sa.DateTime(timezone=True)),
                sa.UniqueConstraint(
                    "access_id", "dedupe_key", name="uq_guest_notice_dedupe"
                ),
            ]
        else:
            columns += [
                sa.Column("client_reference", UUID(), nullable=False),
                sa.Column("question", sa.String(2000), nullable=False),
                sa.Column("answer", sa.Text(), nullable=False),
                sa.Column("sources", JSONB(), nullable=False),
                sa.UniqueConstraint(
                    "access_id", "client_reference", name="uq_guest_ai_command"
                ),
            ]
        op.create_table(table, *columns)
    op.create_index(
        "ix_guest_ai_messages_access_id", "guest_ai_messages", ["access_id"]
    )
    op.add_column(
        "guest_requests",
        sa.Column(
            "guest_access_id",
            UUID(),
            sa.ForeignKey("guest_access.id", ondelete="SET NULL"),
        ),
    )
    op.add_column("guest_requests", sa.Column("client_reference", UUID()))
    op.add_column("guest_requests", sa.Column("guest_description", sa.Text()))
    op.create_unique_constraint(
        "uq_guest_request_command",
        "guest_requests",
        ["guest_access_id", "client_reference"],
    )
    op.execute(
        "INSERT INTO permissions(id,key,description) VALUES(gen_random_uuid(),'guest_portal.manage','Manage guest portal invitations and published guest information') ON CONFLICT(key) DO NOTHING"
    )
    op.execute(
        "INSERT INTO role_permissions(role_id,permission_id) SELECT r.id,p.id FROM roles r CROSS JOIN permissions p WHERE r.key IN ('lodge_admin','group_admin','front_office') AND p.key='guest_portal.manage' ON CONFLICT DO NOTHING"
    )
    # No guest is ever a staff/group/platform member, even through a future API mistake.
    op.execute(
        """CREATE FUNCTION enforce_guest_identity() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF TG_TABLE_NAME='guest_access' THEN
        IF NOT EXISTS(SELECT 1 FROM users WHERE id=NEW.user_id AND is_guest AND NOT is_super_admin) THEN RAISE EXCEPTION 'Guest identity required'; END IF;
      ELSE
        IF EXISTS(SELECT 1 FROM users WHERE id=CASE WHEN TG_TABLE_NAME='lodge_groups' THEN (to_jsonb(NEW)->>'admin_user_id')::uuid ELSE (to_jsonb(NEW)->>'user_id')::uuid END AND is_guest) THEN RAISE EXCEPTION 'Guests cannot hold internal access'; END IF;
      END IF;
      RETURN NEW; END $$"""
    )
    for table in ["guest_access", "memberships", "staff_profiles", "lodge_groups"]:
        op.execute(
            f"CREATE TRIGGER guest_identity_guard BEFORE INSERT OR UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION enforce_guest_identity()"
        )
    normal = "current_setting('app.guest_mode',true) IS DISTINCT FROM 'true'"
    owner = "user_id::text=current_setting('app.current_user_id',true)"
    tenant = "current_setting('app.is_super_admin',true)='true' OR lodge_id::text=current_setting('app.current_lodge_id',true)"
    for table in [
        "guest_access",
        "guest_portal_content",
        "guest_notices",
        "guest_ai_messages",
    ]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY guest_access_staff ON guest_access USING ({normal} AND ({tenant})) WITH CHECK ({normal} AND ({tenant}))"
    )
    op.execute(
        f"CREATE POLICY guest_access_owner ON guest_access FOR SELECT USING ({owner})"
    )
    op.execute(
        f"CREATE POLICY guest_content_staff ON guest_portal_content USING ({normal} AND ({tenant})) WITH CHECK ({normal} AND ({tenant}))"
    )
    op.execute(
        """CREATE FUNCTION guest_scope_valid() RETURNS boolean LANGUAGE sql STABLE AS $$
      SELECT current_setting('app.guest_mode',true)='true' AND EXISTS (
       SELECT 1 FROM guest_access a JOIN users u ON u.id=a.user_id
       WHERE a.id::text=current_setting('app.guest_access_id',true)
        AND a.lodge_id::text=current_setting('app.guest_lodge_id',true)
        AND a.guest_id::text=current_setting('app.guest_profile_id',true)
        AND a.stay_id::text=current_setting('app.guest_stay_id',true)
        AND a.user_id::text=current_setting('app.current_user_id',true)
        AND a.revoked_at IS NULL AND u.is_guest AND u.is_active AND NOT u.is_super_admin)
    $$"""
    )
    # Existing operational policies are untouched. Guest contexts leave the staff
    # lodge setting empty; only the following explicit projections become readable.
    scopes = {
        "guests": "id::text=current_setting('app.guest_profile_id',true)",
        "stays": "id::text=current_setting('app.guest_stay_id',true) AND guest_id::text=current_setting('app.guest_profile_id',true)",
        "units": "id IN (SELECT unit_id FROM stays WHERE id::text=current_setting('app.guest_stay_id',true))",
        "activity_guests": "guest_id::text=current_setting('app.guest_profile_id',true) AND (stay_id IS NULL OR stay_id::text=current_setting('app.guest_stay_id',true))",
        "activities": "id IN (SELECT activity_id FROM activity_guests WHERE guest_id::text=current_setting('app.guest_profile_id',true)) AND starts_at >= (SELECT arrival_date::timestamp AT TIME ZONE (SELECT timezone FROM lodges WHERE id=activities.lodge_id) FROM stays WHERE id::text=current_setting('app.guest_stay_id',true)) AND starts_at < (SELECT (departure_date+1)::timestamp AT TIME ZONE (SELECT timezone FROM lodges WHERE id=activities.lodge_id) FROM stays WHERE id::text=current_setting('app.guest_stay_id',true))",
        "transfers": "guest_id::text=current_setting('app.guest_profile_id',true) AND stay_id::text=current_setting('app.guest_stay_id',true)",
        "subscriptions": "lodge_id::text=current_setting('app.guest_lodge_id',true)",
        "lodge_entitlement_overrides": "lodge_id::text=current_setting('app.guest_lodge_id',true)",
        "guest_requests": "guest_access_id::text=current_setting('app.guest_access_id',true) AND created_by_user_id::text=current_setting('app.current_user_id',true)",
        "guest_portal_content": "published AND (starts_at IS NULL OR starts_at<=now()) AND (ends_at IS NULL OR ends_at>now())",
    }
    for table, condition in scopes.items():
        op.execute(
            f"CREATE POLICY portal_guest_read ON {table} FOR SELECT USING (guest_scope_valid() AND lodge_id::text=current_setting('app.guest_lodge_id',true) AND ({condition}))"
        )
    for table in ["guest_notices", "guest_ai_messages"]:
        own = f"guest_scope_valid() AND {owner} AND access_id::text=current_setting('app.guest_access_id',true)"
        op.execute(
            f"CREATE POLICY portal_guest_read ON {table} FOR SELECT USING ({own})"
        )
        if table == "guest_ai_messages":
            op.execute(
                f"CREATE POLICY portal_guest_write ON {table} FOR INSERT WITH CHECK ({own})"
            )
            op.execute(
                f"CREATE POLICY portal_guest_delete ON {table} FOR DELETE USING ({own})"
            )
        else:
            op.execute(
                f"CREATE POLICY portal_guest_ack ON {table} FOR UPDATE USING ({own}) WITH CHECK ({own})"
            )
            op.execute(
                f"CREATE POLICY portal_staff_notice ON {table} FOR INSERT WITH CHECK ({normal} AND ({tenant}))"
            )
    op.execute(
        """CREATE POLICY portal_guest_create ON guest_requests FOR INSERT WITH CHECK (
      guest_scope_valid() AND guest_access_id::text=current_setting('app.guest_access_id',true)
      AND guest_id::text=current_setting('app.guest_profile_id',true) AND stay_id::text=current_setting('app.guest_stay_id',true)
      AND lodge_id::text=current_setting('app.guest_lodge_id',true) AND created_by_user_id::text=current_setting('app.current_user_id',true)
      AND status='open' AND priority='normal' AND assigned_staff_id IS NULL AND department_id IS NULL AND task_id IS NULL)
    """
    )
    # These foundation tables were global before this migration. Keep that
    # behaviour for existing authentication/staff code, constrain guest SQL reads.
    for table, column in [
        ("users", "id"),
        ("auth_sessions", "user_id"),
        ("invitations", "user_id"),
        ("password_reset_tokens", "user_id"),
        ("lodges", "id"),
    ]:
        target = "app.guest_lodge_id" if table == "lodges" else "app.current_user_id"
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY portal_foundation_guard ON {table} USING ({normal} OR {column}::text=current_setting('{target}',true)) WITH CHECK ({normal} OR {column}::text=current_setting('{target}',true))"
        )
    op.execute(
        "INSERT INTO plan_entitlements(plan_key,feature_key,enabled) VALUES ('Standard','guest_ai',true),('Premium','guest_ai',true) ON CONFLICT DO NOTHING"
    )


def downgrade():
    for table in [
        "users",
        "auth_sessions",
        "invitations",
        "password_reset_tokens",
        "lodges",
    ]:
        op.execute(f"DROP POLICY portal_foundation_guard ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    for table in [
        "guests",
        "stays",
        "units",
        "activity_guests",
        "activities",
        "transfers",
        "subscriptions",
        "lodge_entitlement_overrides",
        "guest_requests",
        "guest_portal_content",
        "guest_notices",
        "guest_ai_messages",
    ]:
        op.execute(f"DROP POLICY IF EXISTS portal_guest_read ON {table}")
    op.execute("DROP POLICY portal_guest_create ON guest_requests")
    op.execute("DROP POLICY portal_guest_write ON guest_ai_messages")
    op.execute("DROP POLICY portal_guest_delete ON guest_ai_messages")
    op.execute("DROP POLICY portal_guest_ack ON guest_notices")
    op.execute("DROP FUNCTION guest_scope_valid()")
    for table in ["guest_access", "memberships", "staff_profiles", "lodge_groups"]:
        op.execute(f"DROP TRIGGER guest_identity_guard ON {table}")
    op.execute("DROP FUNCTION enforce_guest_identity()")
    op.drop_constraint("uq_guest_request_command", "guest_requests", type_="unique")
    op.drop_column("guest_requests", "guest_description")
    op.drop_column("guest_requests", "client_reference")
    op.drop_column("guest_requests", "guest_access_id")
    for table in [
        "guest_ai_messages",
        "guest_notices",
        "guest_portal_content",
        "guest_access",
    ]:
        op.drop_table(table)
    op.drop_constraint("uq_stay_guest_lodge", "stays", type_="unique")
    op.drop_constraint("ck_user_guest_platform", "users", type_="check")
    op.drop_column("users", "is_guest")
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE key='guest_portal.manage')"
    )
    op.execute(
        "DELETE FROM custom_role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE key='guest_portal.manage')"
    )
    op.execute("DELETE FROM permissions WHERE key='guest_portal.manage'")
    op.execute("DELETE FROM plan_entitlements WHERE feature_key='guest_ai'")

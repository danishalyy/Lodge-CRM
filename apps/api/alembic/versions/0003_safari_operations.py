"""production safari operations

Revision ID: 0003_safari_operations
Revises: 0002_operational_core
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision='0003_safari_operations'
down_revision='0002_operational_core'
branch_labels=None
depends_on=None

TENANT_TABLES=['vehicles','vehicle_checklists','vehicle_checklist_items','fuel_records','activities','activity_guests','transfers','wildlife_sightings','wildlife_media']


def upgrade():
    op.create_table('vehicles',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),
        sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('registration',sa.String(80),nullable=False),sa.Column('name',sa.String(160),nullable=False,server_default=''),
        sa.Column('make',sa.String(100),nullable=False,server_default=''),sa.Column('model',sa.String(100),nullable=False,server_default=''),
        sa.Column('year',sa.Integer()),sa.Column('odometer_km',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('fuel_capacity_litres',sa.Numeric(10,2)),sa.Column('status',sa.String(30),nullable=False,server_default='ready'),
        sa.Column('service_due_odometer_km',sa.Integer()),sa.Column('notes',sa.Text(),nullable=False,server_default=''),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('lodge_id','registration',name='uq_vehicle_lodge_registration'),
        sa.CheckConstraint("status in ('ready','assigned','on_drive','maintenance','out_of_service')",name='ck_vehicle_status'),
        sa.CheckConstraint('odometer_km >= 0',name='ck_vehicle_odometer'))
    op.create_index('ix_vehicles_lodge_id','vehicles',['lodge_id']); op.create_index('ix_vehicles_lodge_status','vehicles',['lodge_id','status'])

    op.create_table('vehicle_checklists',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('vehicle_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('vehicles.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('performed_by_staff_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('staff_profiles.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('checklist_type',sa.String(30),nullable=False,server_default='pre_drive'),sa.Column('status',sa.String(30),nullable=False,server_default='in_progress'),
        sa.Column('odometer_km',sa.Integer()),sa.Column('notes',sa.Text(),nullable=False,server_default=''),
        sa.Column('started_at',sa.DateTime(timezone=True),nullable=False),sa.Column('completed_at',sa.DateTime(timezone=True)),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint("checklist_type in ('pre_drive','post_drive','inspection')",name='ck_vehicle_checklist_type'),
        sa.CheckConstraint("status in ('in_progress','passed','failed')",name='ck_vehicle_checklist_status'))
    op.create_index('ix_vehicle_checklists_lodge_id','vehicle_checklists',['lodge_id']); op.create_index('ix_checklists_vehicle_created','vehicle_checklists',['vehicle_id','created_at'])

    op.create_table('vehicle_checklist_items',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('checklist_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('vehicle_checklists.id',ondelete='CASCADE'),nullable=False),
        sa.Column('item_key',sa.String(80),nullable=False),sa.Column('label',sa.String(180),nullable=False),sa.Column('result',sa.String(20),nullable=False,server_default='pending'),
        sa.Column('notes',sa.Text(),nullable=False,server_default=''),
        sa.UniqueConstraint('checklist_id','item_key',name='uq_checklist_item_key'),
        sa.CheckConstraint("result in ('pending','pass','fail','not_applicable')",name='ck_checklist_item_result'))
    op.create_index('ix_vehicle_checklist_items_lodge_id','vehicle_checklist_items',['lodge_id']); op.create_index('ix_checklist_items_checklist','vehicle_checklist_items',['checklist_id'])

    op.create_table('fuel_records',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('vehicle_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('vehicles.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('recorded_by_staff_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('staff_profiles.id',ondelete='RESTRICT')),
        sa.Column('litres',sa.Numeric(10,2),nullable=False),sa.Column('odometer_km',sa.Integer(),nullable=False),sa.Column('cost_cents',sa.Integer()),
        sa.Column('supplier',sa.String(180),nullable=False,server_default=''),sa.Column('reference',sa.String(180),nullable=False,server_default=''),sa.Column('notes',sa.Text(),nullable=False,server_default=''),
        sa.Column('recorded_at',sa.DateTime(timezone=True),nullable=False),sa.Column('created_by_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.CheckConstraint('litres > 0',name='ck_fuel_litres'),sa.CheckConstraint('odometer_km >= 0',name='ck_fuel_odometer'),sa.CheckConstraint('cost_cents IS NULL OR cost_cents >= 0',name='ck_fuel_cost'))
    op.create_index('ix_fuel_records_lodge_id','fuel_records',['lodge_id']); op.create_index('ix_fuel_vehicle_recorded','fuel_records',['vehicle_id','recorded_at'])

    op.create_table('activities',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('activity_type',sa.String(80),nullable=False),sa.Column('title',sa.String(180),nullable=False),
        sa.Column('starts_at',sa.DateTime(timezone=True),nullable=False),sa.Column('ends_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('guide_staff_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('staff_profiles.id',ondelete='SET NULL')),
        sa.Column('vehicle_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('vehicles.id',ondelete='SET NULL')),
        sa.Column('status',sa.String(30),nullable=False,server_default='scheduled'),sa.Column('meeting_point',sa.String(180),nullable=False,server_default=''),sa.Column('notes',sa.Text(),nullable=False,server_default=''),
        sa.Column('created_by_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint('ends_at > starts_at',name='ck_activity_times'),sa.CheckConstraint("status in ('scheduled','confirmed','in_progress','completed','cancelled')",name='ck_activity_status'))
    op.create_index('ix_activities_lodge_id','activities',['lodge_id']); op.create_index('ix_activities_lodge_start','activities',['lodge_id','starts_at']); op.create_index('ix_activities_guide_start','activities',['guide_staff_id','starts_at'])

    op.create_table('activity_guests',
        sa.Column('activity_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('activities.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('guest_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('guests.id',ondelete='RESTRICT'),primary_key=True),
        sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('stay_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('stays.id',ondelete='SET NULL')),
        sa.Column('notes',sa.Text(),nullable=False,server_default=''))
    op.create_index('ix_activity_guests_lodge_id','activity_guests',['lodge_id']); op.create_index('ix_activity_guests_guest','activity_guests',['guest_id'])

    op.create_table('transfers',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('transfer_type',sa.String(30),nullable=False),sa.Column('guest_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('guests.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('stay_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('stays.id',ondelete='SET NULL')),sa.Column('driver_staff_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('staff_profiles.id',ondelete='SET NULL')),
        sa.Column('vehicle_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('vehicles.id',ondelete='SET NULL')),sa.Column('scheduled_at',sa.DateTime(timezone=True),nullable=False),sa.Column('expected_end_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('pickup_location',sa.String(240),nullable=False),sa.Column('dropoff_location',sa.String(240),nullable=False),sa.Column('flight_number',sa.String(80),nullable=False,server_default=''),sa.Column('flight_time',sa.DateTime(timezone=True)),
        sa.Column('passenger_count',sa.Integer(),nullable=False,server_default='1'),sa.Column('status',sa.String(30),nullable=False,server_default='scheduled'),sa.Column('notes',sa.Text(),nullable=False,server_default=''),
        sa.Column('created_by_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint("transfer_type in ('pickup','dropoff','guest_transfer','other')",name='ck_transfer_type'),sa.CheckConstraint("status in ('scheduled','confirmed','en_route','arrived','completed','cancelled')",name='ck_transfer_status'),sa.CheckConstraint('passenger_count >= 1',name='ck_transfer_passengers'),sa.CheckConstraint('expected_end_at > scheduled_at',name='ck_transfer_times'))
    op.create_index('ix_transfers_lodge_id','transfers',['lodge_id']); op.create_index('ix_transfers_lodge_scheduled','transfers',['lodge_id','scheduled_at'])

    op.create_table('wildlife_sightings',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('client_ref',postgresql.UUID(as_uuid=True),nullable=False),sa.Column('species',sa.String(180),nullable=False),sa.Column('notes',sa.Text(),nullable=False,server_default=''),
        sa.Column('latitude',sa.Numeric(9,6)),sa.Column('longitude',sa.Numeric(9,6)),sa.Column('gps_accuracy_m',sa.Numeric(10,2)),
        sa.Column('observed_at',sa.DateTime(timezone=True),nullable=False),sa.Column('reported_by_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='SET NULL')),
        sa.Column('reported_by_staff_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('staff_profiles.id',ondelete='SET NULL')),sa.Column('activity_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('activities.id',ondelete='SET NULL')),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('lodge_id','client_ref',name='uq_sighting_lodge_client_ref'),
        sa.CheckConstraint('latitude IS NULL OR (latitude >= -90 AND latitude <= 90)',name='ck_sighting_latitude'),sa.CheckConstraint('longitude IS NULL OR (longitude >= -180 AND longitude <= 180)',name='ck_sighting_longitude'),sa.CheckConstraint('gps_accuracy_m IS NULL OR gps_accuracy_m >= 0',name='ck_sighting_accuracy'))
    op.create_index('ix_wildlife_sightings_lodge_id','wildlife_sightings',['lodge_id']); op.create_index('ix_sightings_lodge_observed','wildlife_sightings',['lodge_id','observed_at'])

    op.create_table('wildlife_media',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('sighting_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('wildlife_sightings.id',ondelete='CASCADE'),nullable=False),
        sa.Column('object_key',sa.String(600),nullable=False),sa.Column('content_type',sa.String(120),nullable=False),sa.Column('size_bytes',sa.Integer(),nullable=False),sa.Column('sha256',sa.String(64),nullable=False),
        sa.Column('uploaded_by_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='SET NULL')),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('lodge_id','object_key',name='uq_wildlife_media_object_key'),sa.CheckConstraint('size_bytes > 0',name='ck_wildlife_media_size'))
    op.create_index('ix_wildlife_media_lodge_id','wildlife_media',['lodge_id']); op.create_index('ix_wildlife_media_sighting','wildlife_media',['sighting_id'])

    op.add_column('maintenance_tickets',sa.Column('vehicle_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('vehicles.id',ondelete='SET NULL')))
    op.create_index('ix_maintenance_tickets_vehicle_id','maintenance_tickets',['vehicle_id'])

    for table in TENANT_TABLES:
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f'''CREATE POLICY {table}_tenant_policy ON {table} USING (current_setting('app.is_super_admin', true)='true' OR lodge_id::text = current_setting('app.current_lodge_id', true)) WITH CHECK (current_setting('app.is_super_admin', true)='true' OR lodge_id::text = current_setting('app.current_lodge_id', true))''')

    permissions={
      'vehicles.view':'View fleet','vehicles.manage':'Create and update vehicles',
      'vehicle_checklists.view':'View vehicle checklists','vehicle_checklists.manage':'Perform vehicle checklists',
      'fuel.view':'View fuel records','fuel.manage':'Record fuel transactions',
      'activities.view':'View lodge activities','activities.manage':'Create and manage lodge activities',
      'transfers.view':'View guest transfers','transfers.manage':'Create and manage guest transfers',
      'wildlife.view':'View wildlife sightings','wildlife.manage':'Record wildlife sightings',
      'ranger.view':'View ranger operational workspace'
    }
    for key,desc in permissions.items():
        op.execute(sa.text("INSERT INTO permissions (id,key,description) VALUES (gen_random_uuid(),:k,:d) ON CONFLICT (key) DO NOTHING").bindparams(k=key,d=desc))
    role_map={
      'lodge_admin':list(permissions.keys()),
      'department_manager':['vehicles.view','vehicle_checklists.view','fuel.view','activities.view','activities.manage','transfers.view','wildlife.view','ranger.view'],
      'front_office':['vehicles.view','activities.view','activities.manage','transfers.view','transfers.manage','wildlife.view'],
      'ranger':['vehicles.view','vehicle_checklists.view','vehicle_checklists.manage','fuel.view','fuel.manage','activities.view','activities.manage','wildlife.view','wildlife.manage','ranger.view'],
      'housekeeping':[],
      'maintenance':['vehicles.view','vehicles.manage','vehicle_checklists.view','fuel.view'],
      'driver':['vehicles.view','vehicle_checklists.view','vehicle_checklists.manage','fuel.view','fuel.manage','transfers.view','transfers.manage'],
      'fb':['activities.view'],
      'finance':['vehicles.view','fuel.view'],
      'general_staff':['activities.view'],
      'read_only':['vehicles.view','vehicle_checklists.view','fuel.view','activities.view','transfers.view','wildlife.view']
    }
    for role_key,perm_keys in role_map.items():
        for perm in perm_keys:
            op.execute(sa.text("""INSERT INTO role_permissions(role_id,permission_id)
              SELECT r.id,p.id FROM roles r,permissions p WHERE r.key=:r AND p.key=:p ON CONFLICT DO NOTHING""").bindparams(r=role_key,p=perm))


def downgrade():
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE key IN ('vehicles.view','vehicles.manage','vehicle_checklists.view','vehicle_checklists.manage','fuel.view','fuel.manage','activities.view','activities.manage','transfers.view','transfers.manage','wildlife.view','wildlife.manage','ranger.view'))")
    op.execute("DELETE FROM permissions WHERE key IN ('vehicles.view','vehicles.manage','vehicle_checklists.view','vehicle_checklists.manage','fuel.view','fuel.manage','activities.view','activities.manage','transfers.view','transfers.manage','wildlife.view','wildlife.manage','ranger.view')")
    op.drop_index('ix_maintenance_tickets_vehicle_id',table_name='maintenance_tickets'); op.drop_column('maintenance_tickets','vehicle_id')
    for t in reversed(TENANT_TABLES): op.drop_table(t)

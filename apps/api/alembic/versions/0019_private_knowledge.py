"""Private knowledge documents and versioned pgvector chunks."""

from alembic import op

revision = "0019_private_knowledge"
down_revision = "0018_ai_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        "ALTER TABLE departments ADD CONSTRAINT uq_department_knowledge_scope UNIQUE(id,lodge_id)"
    )
    op.execute(
        """CREATE TABLE ai_knowledge_documents (
      id uuid PRIMARY KEY, lodge_id uuid NOT NULL REFERENCES lodges(id) ON DELETE CASCADE,
      created_by uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
      department_id uuid, title varchar(160) NOT NULL, file_name varchar(160) NOT NULL,
      source_type varchar(8) NOT NULL CHECK(source_type IN ('pdf','docx','txt')),
      object_key varchar(400) UNIQUE NOT NULL, sha256 varchar(64) NOT NULL,
      size_bytes integer NOT NULL CHECK(size_bytes > 0 AND size_bytes <= 10485760),
      visibility varchar(20) NOT NULL CHECK(visibility IN ('private','department','lodge')),
      status varchar(20) NOT NULL CHECK(status IN ('uploaded','queued','processing','ready','failed','deleted')),
      error_code varchar(40) NOT NULL, chunk_count integer NOT NULL,
      embedding_model varchar(160) NOT NULL, embedding_version varchar(80) NOT NULL,
      job_token uuid, processing_actor_id uuid REFERENCES users(id), lease_expires_at timestamptz,
      created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
      CONSTRAINT uq_knowledge_scope UNIQUE(id,lodge_id),
      FOREIGN KEY(department_id,lodge_id) REFERENCES departments(id,lodge_id),
      CHECK((visibility='department' AND department_id IS NOT NULL) OR (visibility!='department' AND department_id IS NULL))
    )"""
    )
    op.execute(
        """CREATE TABLE ai_knowledge_chunks (
      id uuid PRIMARY KEY, document_id uuid NOT NULL, lodge_id uuid NOT NULL REFERENCES lodges(id) ON DELETE CASCADE,
      position integer NOT NULL, locator varchar(80) NOT NULL, content text NOT NULL,
      embedding vector(384) NOT NULL, created_at timestamptz NOT NULL,
      FOREIGN KEY(document_id,lodge_id) REFERENCES ai_knowledge_documents(id,lodge_id) ON DELETE CASCADE,
      CONSTRAINT uq_knowledge_chunk_position UNIQUE(document_id,position)
    )"""
    )
    op.execute(
        "CREATE INDEX ix_knowledge_lodge_status ON ai_knowledge_documents(lodge_id,status,created_at)"
    )
    op.execute(
        "CREATE INDEX ix_knowledge_chunk_document ON ai_knowledge_chunks(lodge_id,document_id)"
    )
    # Exact vector scan over an authorised MATERIALIZED relation is intentional:
    # no global ANN search followed by tenant/visibility filtering.
    scope = """lodge_id::text=current_setting('app.current_lodge_id',true)
      AND EXISTS(SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id
        WHERE m.lodge_id=ai_knowledge_documents.lodge_id AND m.is_active AND u.is_active AND NOT u.is_super_admin
        AND m.user_id::text=current_setting('app.current_user_id',true))
      AND (visibility='lodge' OR created_by::text=current_setting('app.current_user_id',true)
        OR (visibility='department' AND department_id IN (
          SELECT COALESCE(m.department_id,s.department_id) FROM memberships m
          LEFT JOIN staff_profiles s ON s.lodge_id=m.lodge_id AND s.user_id=m.user_id
          WHERE m.lodge_id=ai_knowledge_documents.lodge_id AND m.is_active
            AND m.user_id::text=current_setting('app.current_user_id',true))))"""
    for table in ("ai_knowledge_documents", "ai_knowledge_chunks"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY knowledge_visibility ON ai_knowledge_documents USING ({scope}) WITH CHECK ({scope})"
    )
    child = """lodge_id::text=current_setting('app.current_lodge_id',true) AND EXISTS(
      SELECT 1 FROM ai_knowledge_documents d WHERE d.id=document_id AND d.lodge_id=ai_knowledge_chunks.lodge_id)"""
    op.execute(
        f"CREATE POLICY knowledge_chunk_visibility ON ai_knowledge_chunks USING ({child}) WITH CHECK ({child})"
    )
    for key, description in [
        ("knowledge.view", "Read permitted private lodge knowledge"),
        ("knowledge.manage", "Manage approved lodge knowledge documents"),
    ]:
        op.execute(
            f"INSERT INTO permissions(id,key,description) VALUES(gen_random_uuid(),'{key}','{description}') ON CONFLICT(key) DO NOTHING"
        )
    op.execute(
        """INSERT INTO role_permissions(role_id,permission_id)
      SELECT r.id,p.id FROM roles r,permissions p
      WHERE r.key IN ('lodge_admin','group_admin') AND p.key IN ('knowledge.view','knowledge.manage') ON CONFLICT DO NOTHING"""
    )


def downgrade():
    op.execute("DROP TABLE ai_knowledge_chunks")
    op.execute("DROP TABLE ai_knowledge_documents")
    op.execute("ALTER TABLE departments DROP CONSTRAINT uq_department_knowledge_scope")
    op.execute(
        "DELETE FROM custom_role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE key IN ('knowledge.view','knowledge.manage'))"
    )
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE key IN ('knowledge.view','knowledge.manage'))"
    )
    op.execute(
        "DELETE FROM permissions WHERE key IN ('knowledge.view','knowledge.manage')"
    )
    # Extension may be shared by other applications: never DROP EXTENSION CASCADE.

"""Add controlled drugs tables

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3g4h5i6
Create Date: 2026-01-03 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e2f3a4b5c6d7'
down_revision = 'd1e2f3g4h5i6'
branch_labels = None
depends_on = None


def _sqlite_table_exists(bind, name: str) -> bool:
    try:
        res = bind.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"), {'n': name}).fetchall()
        return bool(res)
    except Exception:
        return False


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    def create_if_missing(table_name: str, create_fn):
        if dialect == 'sqlite':
            if _sqlite_table_exists(bind, table_name):
                return
        try:
            create_fn()
        except Exception:
            # If table already exists or dialect limitations, ignore
            pass

    create_if_missing('controlled_drugs', lambda: op.create_table(
        'controlled_drugs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('controlled_drug_number', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('specification', sa.Text(), nullable=True),
        sa.Column('buying_price', sa.Numeric(10, 2), nullable=False),
        sa.Column('selling_price', sa.Numeric(10, 2), nullable=False),
        sa.Column('stocked_quantity', sa.Integer(), nullable=False),
        sa.Column('sold_quantity', sa.Integer(), nullable=True),
        sa.Column('expiry_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('controlled_drug_number')
    ))

    create_if_missing('controlled_prescriptions', lambda: op.create_table(
        'controlled_prescriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('doctor_id', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['patient_id'], ['patient.id']),
        sa.ForeignKeyConstraint(['doctor_id'], ['user.id']),
    ))

    create_if_missing('controlled_prescription_items', lambda: op.create_table(
        'controlled_prescription_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('controlled_prescription_id', sa.Integer(), nullable=False),
        sa.Column('controlled_drug_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('dosage', sa.Text(), nullable=True),
        sa.Column('frequency', sa.String(length=50), nullable=True),
        sa.Column('duration', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['controlled_prescription_id'], ['controlled_prescriptions.id']),
        sa.ForeignKeyConstraint(['controlled_drug_id'], ['controlled_drugs.id']),
    ))

    create_if_missing('controlled_sales', lambda: op.create_table(
        'controlled_sales',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sale_number', sa.String(length=80), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('pharmacist_name', sa.String(length=100), nullable=True),
        sa.Column('total_amount', sa.Float(), nullable=False),
        sa.Column('payment_method', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sale_number'),
        sa.ForeignKeyConstraint(['patient_id'], ['patient.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
    ))

    create_if_missing('controlled_sale_items', lambda: op.create_table(
        'controlled_sale_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sale_id', sa.Integer(), nullable=False),
        sa.Column('controlled_drug_id', sa.Integer(), nullable=False),
        sa.Column('controlled_drug_name', sa.String(length=255), nullable=True),
        sa.Column('controlled_drug_specification', sa.Text(), nullable=True),
        sa.Column('individual_sale_number', sa.String(length=120), nullable=True),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('prescription_source', sa.String(length=20), nullable=False),
        sa.Column('prescription_sheet_path', sa.String(length=500), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=True),
        sa.Column('unit_price', sa.Float(), nullable=False),
        sa.Column('total_price', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['sale_id'], ['controlled_sales.id']),
        sa.ForeignKeyConstraint(['controlled_drug_id'], ['controlled_drugs.id']),
    ))


def downgrade():
    # Drop in reverse dependency order
    try:
        op.drop_table('controlled_sale_items')
    except Exception:
        pass
    try:
        op.drop_table('controlled_sales')
    except Exception:
        pass
    try:
        op.drop_table('controlled_prescription_items')
    except Exception:
        pass
    try:
        op.drop_table('controlled_prescriptions')
    except Exception:
        pass
    try:
        op.drop_table('controlled_drugs')
    except Exception:
        pass

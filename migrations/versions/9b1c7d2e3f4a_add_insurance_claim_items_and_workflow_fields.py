"""Add insurance claim itemization and workflow fields

Revision ID: 9b1c7d2e3f4a
Revises: eed86a9ac164
Create Date: 2026-01-08

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9b1c7d2e3f4a'
down_revision = 'eed86a9ac164'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('insurance_claims', sa.Column('external_reference', sa.String(length=80), nullable=True))
    op.add_column('insurance_claims', sa.Column('approved_by', sa.Integer(), nullable=True))
    op.add_column('insurance_claims', sa.Column('approved_at', sa.DateTime(), nullable=True))
    op.add_column('insurance_claims', sa.Column('rejected_at', sa.DateTime(), nullable=True))
    op.add_column('insurance_claims', sa.Column('rejected_reason', sa.Text(), nullable=True))

    op.create_table(
        'insurance_claim_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('claim_id', sa.Integer(), nullable=False),
        sa.Column('sale_item_id', sa.Integer(), nullable=False),
        sa.Column('item_type', sa.String(length=30), nullable=True),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=True),
        sa.Column('unit_price', sa.Float(), nullable=True),
        sa.Column('total_price', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['claim_id'], ['insurance_claims.id'], ),
        sa.ForeignKeyConstraint(['sale_item_id'], ['sale_items.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('claim_id', 'sale_item_id', name='uq_insurance_claim_items_claim_sale_item'),
    )


def downgrade():
    op.drop_table('insurance_claim_items')

    op.drop_column('insurance_claims', 'rejected_reason')
    op.drop_column('insurance_claims', 'rejected_at')
    op.drop_column('insurance_claims', 'approved_at')
    op.drop_column('insurance_claims', 'approved_by')
    op.drop_column('insurance_claims', 'external_reference')

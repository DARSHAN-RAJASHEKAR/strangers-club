"""Create initial tables

Revision ID: 3fadb7395c00
Revises: 
Create Date: 2025-06-26 02:50:13.311893

"""
from app.db import types
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3fadb7395c00'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'users' not in inspector.get_table_names():
        op.create_table('users',
        sa.Column('id', types.GUID(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('google_id', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_superuser', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('phone_number', sa.String(), nullable=True),
        sa.Column('phone_verified', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id')
        )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_google_id'), 'users', ['google_id'], unique=True)
    op.create_index(op.f('ix_users_phone_number'), 'users', ['phone_number'], unique=True)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_table('groups',
    sa.Column('id', types.GUID(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('is_general', sa.Boolean(), nullable=True),
    sa.Column('meetup_date', sa.DateTime(timezone=True), nullable=True),
    sa.Column('owner_id', types.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('phone_verifications',
    sa.Column('id', types.GUID(), nullable=False),
    sa.Column('user_id', types.GUID(), nullable=False),
    sa.Column('phone_number', sa.String(), nullable=False),
    sa.Column('verification_code', sa.String(length=6), nullable=False),
    sa.Column('is_verified', sa.Boolean(), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_phone_verifications_phone_number'), 'phone_verifications', ['phone_number'], unique=False)
    op.create_table('channels',
    sa.Column('id', types.GUID(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('type', sa.Enum('GENERAL', 'HOBBY', 'INTEREST', 'MEETUP', 'OTHER', name='channeltype'), nullable=True),
    sa.Column('group_id', types.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('invitations',
    sa.Column('id', types.GUID(), nullable=False),
    sa.Column('code', sa.String(), nullable=False),
    sa.Column('inviter_id', types.GUID(), nullable=False),
    sa.Column('invitee_id', types.GUID(), nullable=True),
    sa.Column('group_id', types.GUID(), nullable=False),
    sa.Column('is_used', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ),
    sa.ForeignKeyConstraint(['invitee_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['inviter_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_invitations_code'), 'invitations', ['code'], unique=True)
    op.create_table('user_group',
    sa.Column('user_id', types.GUID(), nullable=False),
    sa.Column('group_id', types.GUID(), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user_id', 'group_id')
    )
    op.create_table('messages',
    sa.Column('id', types.GUID(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('author_id', types.GUID(), nullable=False),
    sa.Column('channel_id', types.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('messages')
    op.drop_table('user_group')
    op.drop_index(op.f('ix_invitations_code'), table_name='invitations')
    op.drop_table('invitations')
    op.drop_table('channels')
    op.drop_index(op.f('ix_phone_verifications_phone_number'), table_name='phone_verifications')
    op.drop_table('phone_verifications')
    op.drop_table('groups')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_phone_number'), table_name='users')
    op.drop_index(op.f('ix_users_google_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    # ### end Alembic commands ###

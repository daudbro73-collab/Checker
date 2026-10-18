"""initial schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-21 22:56:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_id', sa.Integer(), nullable=True),
        sa.Column('username', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('hashed_password', sa.String(), nullable=True),
        sa.Column('balance', sa.Float(), nullable=True, default=0.0),
        sa.Column('check_credits', sa.Integer(), nullable=True, default=0),
        sa.Column('is_admin', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('referral_code', sa.String(), nullable=True),
        sa.Column('referrer_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('subscription_expires_at', sa.DateTime(), nullable=True),
        sa.Column('subscription_checks_left', sa.Integer(), nullable=True, default=0),
        sa.Column('free_check_used', sa.Boolean(), nullable=True, default=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_telegram_id'), 'users', ['telegram_id'], unique=True)
    op.create_index(op.f('ix_users_referral_code'), 'users', ['referral_code'], unique=True)

    # 2. deposit_addresses
    op.create_table(
        'deposit_addresses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('chain', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True, default='standby'),
        sa.Column('slot', sa.Integer(), nullable=True),
        sa.Column('balance_usdt', sa.Float(), nullable=True, default=0.0),
        sa.Column('reserved_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reserved_until', sa.DateTime(), nullable=True),
        sa.Column('last_assigned_at', sa.DateTime(), nullable=True),
        sa.Column('last_screened_at', sa.DateTime(), nullable=True),
        sa.Column('last_sweep_at', sa.DateTime(), nullable=True),
        sa.Column('quarantine_reason', sa.Text(), nullable=True),
        sa.Column('quarantined_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_deposit_addresses_id'), 'deposit_addresses', ['id'], unique=False)
    op.create_index(op.f('ix_deposit_addresses_address'), 'deposit_addresses', ['address'], unique=False)
    op.create_index(op.f('ix_deposit_addresses_chain'), 'deposit_addresses', ['chain'], unique=False)
    op.create_index(op.f('ix_deposit_addresses_status'), 'deposit_addresses', ['status'], unique=False)

    # 3. payments
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(), nullable=True, default='USDT'),
        sa.Column('status', sa.String(), nullable=True, default='pending'),
        sa.Column('tx_hash', sa.String(), nullable=True),
        sa.Column('product', sa.String(), nullable=True),
        sa.Column('deposit_address_id', sa.Integer(), sa.ForeignKey('deposit_addresses.id'), nullable=True),
        sa.Column('sender_address', sa.String(), nullable=True),
        sa.Column('screening_status', sa.String(), nullable=True),
        sa.Column('screening_detail', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_payments_id'), 'payments', ['id'], unique=False)

    # 4. deposit_sweep_logs
    op.create_table(
        'deposit_sweep_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('deposit_address_id', sa.Integer(), sa.ForeignKey('deposit_addresses.id'), nullable=True),
        sa.Column('chain', sa.String(), nullable=True),
        sa.Column('balance_usdt', sa.Float(), nullable=True, default=0.0),
        sa.Column('senders_json', sa.Text(), nullable=True),
        sa.Column('screening_result', sa.String(), nullable=True),
        sa.Column('action', sa.String(), nullable=True),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_deposit_sweep_logs_id'), 'deposit_sweep_logs', ['id'], unique=False)

    # 5. check_history
    op.create_table(
        'check_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('chain', sa.String(), nullable=True),
        sa.Column('risk_score', sa.Integer(), nullable=True),
        sa.Column('risk_level', sa.String(), nullable=True),
        sa.Column('payload_json', sa.Text(), nullable=True),
        sa.Column('list_versions_json', sa.Text(), nullable=True),
        sa.Column('is_free', sa.Boolean(), nullable=True, default=False),
        sa.Column('share_token', sa.String(), nullable=True),
        sa.Column('share_expires_at', sa.DateTime(), nullable=True),
        sa.Column('report_id', sa.String(), nullable=True),
        sa.Column('sha256_hash', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_check_history_id'), 'check_history', ['id'], unique=False)
    op.create_index(op.f('ix_check_history_address'), 'check_history', ['address'], unique=False)
    op.create_index(op.f('ix_check_history_share_token'), 'check_history', ['share_token'], unique=True)
    op.create_index(op.f('ix_check_history_report_id'), 'check_history', ['report_id'], unique=True)
    op.create_index(op.f('ix_check_history_sha256_hash'), 'check_history', ['sha256_hash'], unique=False)

    # 6. sanctioned_addresses
    op.create_table(
        'sanctioned_addresses',
        sa.Column('address', sa.String(), primary_key=True),
        sa.Column('currency', sa.String(), nullable=True),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('entity_name', sa.String(), nullable=True),
        sa.Column('source_url', sa.String(), nullable=True),
        sa.Column('listed_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index(op.f('ix_sanctioned_addresses_address'), 'sanctioned_addresses', ['address'], unique=False)
    op.create_index(op.f('ix_sanctioned_addresses_currency'), 'sanctioned_addresses', ['currency'], unique=False)

    # 7. risk_labels
    op.create_table(
        'risk_labels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('chain', sa.String(), nullable=True),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('label', sa.String(), nullable=True),
        sa.Column('confidence', sa.String(), nullable=True, default='medium'),
        sa.Column('source_url', sa.String(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_risk_labels_id'), 'risk_labels', ['id'], unique=False)
    op.create_index(op.f('ix_risk_labels_address'), 'risk_labels', ['address'], unique=False)

    # 8. list_snapshots
    op.create_table(
        'list_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('version', sa.String(), nullable=True),
        sa.Column('record_count', sa.Integer(), nullable=True, default=0),
        sa.Column('synced_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_list_snapshots_id'), 'list_snapshots', ['id'], unique=False)
    op.create_index(op.f('ix_list_snapshots_source'), 'list_snapshots', ['source'], unique=False)

    # 9. disputes
    op.create_table(
        'disputes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('check_id', sa.Integer(), sa.ForeignKey('check_history.id'), nullable=True),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('chain', sa.String(), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=True, default='open'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_disputes_id'), 'disputes', ['id'], unique=False)

    # 10. address_monitors
    op.create_table(
        'address_monitors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('chain', sa.String(), nullable=True),
        sa.Column('label', sa.String(), nullable=True),
        sa.Column('last_score', sa.Integer(), nullable=True),
        sa.Column('last_level', sa.String(), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.Column('notify_telegram', sa.Boolean(), nullable=True, default=True),
        sa.Column('active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_address_monitors_id'), 'address_monitors', ['id'], unique=False)
    op.create_index(op.f('ix_address_monitors_address'), 'address_monitors', ['address'], unique=False)

    # 11. api_keys
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('key_hash', sa.String(), nullable=True),
        sa.Column('key_prefix', sa.String(), nullable=True),
        sa.Column('plan', sa.String(), nullable=True, default='api_starter'),
        sa.Column('quota_monthly', sa.Integer(), nullable=True, default=500),
        sa.Column('used_this_month', sa.Integer(), nullable=True, default=0),
        sa.Column('active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_api_keys_id'), 'api_keys', ['id'], unique=False)
    op.create_index(op.f('ix_api_keys_key_hash'), 'api_keys', ['key_hash'], unique=True)


def downgrade() -> None:
    op.drop_table('api_keys')
    op.drop_table('address_monitors')
    op.drop_table('disputes')
    op.drop_table('list_snapshots')
    op.drop_table('risk_labels')
    op.drop_table('sanctioned_addresses')
    op.drop_table('check_history')
    op.drop_table('deposit_sweep_logs')
    op.drop_table('payments')
    op.drop_table('deposit_addresses')
    op.drop_table('users')

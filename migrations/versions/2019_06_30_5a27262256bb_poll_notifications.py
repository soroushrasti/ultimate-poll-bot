"""Poll notifications

Revision ID: 5a27262256bb
Revises: b0789eb1e8a4
Create Date: 2019-06-30 21:45:28.554097

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5a27262256bb"
down_revision = "b0789eb1e8a4"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "notification",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("select_message_id", sa.BigInteger(), nullable=True),
        sa.Column("poll_message_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("poll_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["poll_id"], ["poll.id"], ondelete="cascade"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "poll_id", "chat_id", name="one_notification_per_poll_and_chat"
        ),
    )
    op.create_index(
        op.f("ix_notification_poll_id"), "notification", ["poll_id"], unique=False
    )
    op.add_column("poll", sa.Column("next_notification", sa.DateTime(), nullable=True))
    op.alter_column(
        "poll",
        "due_date",
        existing_type=sa.DATE(),
        type_=sa.DateTime(),
        existing_nullable=True,
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "poll",
        "due_date",
        existing_type=sa.DateTime(),
        type_=sa.DATE(),
        existing_nullable=True,
    )
    op.drop_column("poll", "next_notification")
    op.drop_index(op.f("ix_notification_poll_id"), table_name="notification")
    op.drop_table("notification")
    # ### end Alembic commands ###

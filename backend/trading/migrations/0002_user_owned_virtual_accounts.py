# T-010: VirtualAccount를 Django 사용자와 1:1로 연결하고 기존 singleton 제약을 제거한다.
# 기존 단일 계좌·원장·주문·가격·수집 실행 기록은 삭제·복제·재계산하지 않는다.
# SeparateDatabaseAndState로 (1) Django state를 갱신하고, (2) 실제 DDL은 재실행 안전한
# idempotent SQL로 처리한다. owner는 NULL로 추가되어 기존 계좌는 연결 전까지 legacy로 남는다.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

_FORWARD_SQL = """
ALTER TABLE virtual_accounts ADD COLUMN IF NOT EXISTS owner_id BIGINT;
-- 사용자당 계좌 1개(1:1). Postgres 유일 인덱스는 여러 NULL을 허용하므로 legacy 1건과 공존한다.
CREATE UNIQUE INDEX IF NOT EXISTS virtual_accounts_owner_id_key ON virtual_accounts (owner_id);
-- auth_user 외래키(있을 때만 추가).
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'virtual_accounts_owner_id_fk') THEN
        ALTER TABLE virtual_accounts
            ADD CONSTRAINT virtual_accounts_owner_id_fk FOREIGN KEY (owner_id)
            REFERENCES auth_user (id) DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;
-- 단일 계좌 제약 제거: singleton 컬럼을 내리면 인라인 UNIQUE·CHECK 제약도 함께 제거된다.
ALTER TABLE virtual_accounts DROP COLUMN IF EXISTS singleton;
"""

# 역방향: 0001 상태(singleton 존재, owner 없음)로 되돌린다. migration executor 테스트에서 사용한다.
_REVERSE_SQL = """
ALTER TABLE virtual_accounts ADD COLUMN IF NOT EXISTS singleton BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE virtual_accounts DROP CONSTRAINT IF EXISTS virtual_accounts_owner_id_fk;
DROP INDEX IF EXISTS virtual_accounts_owner_id_key;
ALTER TABLE virtual_accounts DROP COLUMN IF EXISTS owner_id;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="virtualaccount",
                    name="owner",
                    field=models.OneToOneField(
                        blank=True, null=True, db_column="owner_id",
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="virtual_account", to=settings.AUTH_USER_MODEL,
                    ),
                ),
                migrations.RemoveConstraint(
                    model_name="virtualaccount", name="virtual_accounts_singleton_true",
                ),
                migrations.RemoveField(model_name="virtualaccount", name="singleton"),
            ],
            database_operations=[
                migrations.RunSQL(sql=_FORWARD_SQL, reverse_sql=_REVERSE_SQL),
            ],
        ),
    ]

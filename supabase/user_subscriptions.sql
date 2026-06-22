-- User Subscriptions Table
-- 用于管理用户订阅状态（Early Adopter 月付/年付，以及未来的 Regular 定价）

CREATE TABLE IF NOT EXISTS user_subscriptions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    plan TEXT NOT NULL DEFAULT 'free',  -- 'free', 'early_adopter_monthly', 'early_adopter_yearly', 'regular'
    status TEXT NOT NULL DEFAULT 'active',  -- 'active', 'canceled', 'expired', 'scheduled_cancel'
    creem_subscription_id TEXT,  -- Creem 订阅 ID
    creem_customer_id TEXT,  -- Creem 客户 ID
    current_period_start TIMESTAMPTZ,  -- 当前计费周期开始时间
    current_period_end TIMESTAMPTZ,  -- 当前计费周期结束时间
    canceled_at TIMESTAMPTZ,  -- 取消时间
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(creem_subscription_id)
);

-- 索引：按用户查询订阅
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id ON user_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_status ON user_subscriptions(status);

-- RLS 策略
ALTER TABLE user_subscriptions ENABLE ROW LEVEL SECURITY;

-- 用户只能查看自己的订阅
CREATE POLICY "Users can view own subscription" ON user_subscriptions
    FOR SELECT USING (auth.uid() = user_id);

-- Service Role 可以操作所有订阅（后端使用 service_role_key）
-- 注意：如果你的后端使用 service_role_key，则不需要额外的 RLS 策略
-- 如果使用 anon key，需要添加 INSERT/UPDATE 策略

-- 更新 user_credits 表的免费次数（从 2 改为 3）
-- 注意：这只影响新用户。已有用户需要手动更新。
-- UPDATE user_credits SET credits_remaining = credits_remaining + 1 WHERE credits_remaining < 3;

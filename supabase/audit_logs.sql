-- Audit Logs Table
-- 审计日志表：记录用户操作

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    action VARCHAR(50) NOT NULL,  -- 操作类型
    user_id VARCHAR(255),         -- 用户 ID
    user_email VARCHAR(255),      -- 用户邮箱（本地用户可能没有 ID）
    resource_id VARCHAR(255),     -- 相关资源 ID
    resource_type VARCHAR(50),    -- 资源类型
    details JSONB DEFAULT '{}',   -- 额外详情
    ip_address VARCHAR(50),       -- 客户端 IP
    user_agent TEXT,              -- 客户端 User-Agent
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);

-- Row Level Security (RLS)
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- 只有管理员可以查看审计日志
-- 注意：需要在 Supabase 中创建一个 is_admin 函数或使用其他方式验证管理员权限
-- 这里暂时允许所有 authenticated 用户查看（实际应用中需要更严格的控制）

-- 管理员可以查看所有日志
CREATE POLICY "Admins can view all audit logs" ON audit_logs
    FOR SELECT
    USING (
        -- 检查是否是本地管理员（通过 user_email 匹配）
        user_email = 'admin' OR
        -- 或者使用自定义的 admin 角色（需要在 auth.users 表中添加 role 字段）
        EXISTS (
            SELECT 1 FROM auth.users
            WHERE auth.users.id = auth.uid()
            AND auth.users.raw_user_meta_data->>'role' = 'admin'
        )
    );

-- 所有 authenticated 用户可以插入审计日志
CREATE POLICY "Authenticated users can insert audit logs" ON audit_logs
    FOR INSERT
    WITH CHECK (auth.role() = 'authenticated' OR auth.role() = 'anon');

-- 匿名用户也可以插入审计日志（用于记录未登录用户的操作）
CREATE POLICY "Anonymous users can insert audit logs" ON audit_logs
    FOR INSERT
    WITH CHECK (true);
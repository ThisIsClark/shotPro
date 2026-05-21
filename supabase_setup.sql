-- Supabase Database Setup
-- Execute this SQL in Supabase Dashboard > SQL Editor

-- 分析记录表（替代内存 task_store）
CREATE TABLE IF NOT EXISTS analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,  -- 关联 Supabase Auth 用户
    video_filename VARCHAR(255) NOT NULL,
    video_path VARCHAR(500) NOT NULL,
    result_path VARCHAR(500),
    status VARCHAR(20) DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    error_message TEXT,

    -- 分析配置
    shooting_hand VARCHAR(10) NOT NULL,
    shooting_style VARCHAR(20) NOT NULL,
    template_id VARCHAR(50),
    generate_video BOOLEAN DEFAULT false,
    generate_skeleton_video BOOLEAN DEFAULT false,

    -- 结果摘要
    overall_score FLOAT,
    rating VARCHAR(20),
    total_frames INTEGER,
    fps FLOAT,
    duration FLOAT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- 用户模板表
CREATE TABLE IF NOT EXISTS user_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT false,
    shooting_hand VARCHAR(10) DEFAULT 'right',
    key_frames JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_analyses_user_id ON analyses(user_id);
CREATE INDEX IF NOT EXISTS idx_analyses_status ON analyses(status);
CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_templates_user_id ON user_templates(user_id);
CREATE INDEX IF NOT EXISTS idx_user_templates_public ON user_templates(is_public);

-- 设置 Row Level Security (RLS) 策略
-- 用户只能访问自己的分析记录

ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;

-- 创建策略：用户可以查看自己的分析记录
CREATE POLICY "Users can view own analyses" ON analyses
    FOR SELECT USING (auth.uid() = user_id);

-- 创建策略：用户可以插入自己的分析记录
CREATE POLICY "Users can insert own analyses" ON analyses
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- 创建策略：Service role 可以管理所有记录（用于后端）
CREATE POLICY "Service role full access" ON analyses
    FOR ALL USING (auth.role() = 'service_role');

-- 用户模板表的 RLS
ALTER TABLE user_templates ENABLE ROW LEVEL SECURITY;

-- 用户可以查看自己的模板和公开模板
CREATE POLICY "Users can view own and public templates" ON user_templates
    FOR SELECT USING (auth.uid() = user_id OR is_public = true);

-- 用户可以插入自己的模板
CREATE POLICY "Users can insert own templates" ON user_templates
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- 用户可以删除自己的模板
CREATE POLICY "Users can delete own templates" ON user_templates
    FOR DELETE USING (auth.uid() = user_id);

-- Service role 完全访问
CREATE POLICY "Service role full access on templates" ON user_templates
    FOR ALL USING (auth.role() = 'service_role');
-- ╔══════════════════════════════════════════════════════╗
-- ║   SQL para criação da tabela no Supabase             ║
-- ║   Execute no SQL Editor do painel do Supabase        ║
-- ╚══════════════════════════════════════════════════════╝

-- Habilita extensão UUID (já ativa por padrão no Supabase)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Cria a tabela de agendamentos
CREATE TABLE IF NOT EXISTS agendamentos (
    id         UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    nome       TEXT        NOT NULL,
    servico    TEXT        NOT NULL,
    data       TEXT        NOT NULL,      -- formato: DD/MM/AAAA
    horario    TEXT        NOT NULL,      -- formato: HH:MM
    criado_em  TIMESTAMPTZ DEFAULT NOW()
);

-- Índice para buscas por data
CREATE INDEX IF NOT EXISTS idx_agendamentos_data ON agendamentos(data);

-- Comentários nas colunas
COMMENT ON TABLE  agendamentos          IS 'Agendamentos do Studio Dandara Britto via Telegram Bot';
COMMENT ON COLUMN agendamentos.nome     IS 'Nome completo da cliente';
COMMENT ON COLUMN agendamentos.servico  IS 'Serviço escolhido (Manicure, Pedicure, etc.)';
COMMENT ON COLUMN agendamentos.data     IS 'Data do agendamento no formato DD/MM/AAAA';
COMMENT ON COLUMN agendamentos.horario  IS 'Horário no formato HH:MM';
COMMENT ON COLUMN agendamentos.criado_em IS 'Timestamp de criação do registro';

-- ─── Permissões (Row Level Security) ────────────────────────────────
-- Descomente abaixo se quiser habilitar RLS com política de service_role
-- ALTER TABLE agendamentos ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "service_role_full_access" ON agendamentos
--     FOR ALL USING (auth.role() = 'service_role');

-- ─── Exemplo de consulta ─────────────────────────────────────────────
-- SELECT * FROM agendamentos ORDER BY criado_em DESC;

# 🌸 Studio Dandara Britto — Bot de Agendamento Telegram

Bot de agendamento para o Studio Dandara Britto integrado com Supabase.

## 📦 Instalação

```bash
# 1. Clone / copie os arquivos para uma pasta
cd nail_bot

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Configure as variáveis de ambiente
cp .env.example .env
# Edite o .env com seus dados reais

# 4. Crie a tabela no Supabase
# Cole o conteúdo de supabase_schema.sql no SQL Editor do Supabase

# 5. Execute o bot
python bot.py
```

## 🔑 Variáveis de ambiente

| Variável        | Onde obter                                         |
|-----------------|----------------------------------------------------|
| `TELEGRAM_TOKEN`| @BotFather no Telegram                             |
| `SUPABASE_URL`  | Supabase → Settings → API → Project URL            |
| `SUPABASE_KEY`  | Supabase → Settings → API → `service_role` secret  |

## 🤖 Comandos do bot

| Comando     | Descrição                      |
|-------------|--------------------------------|
| `/start`    | Inicia o bot / exibe o menu    |
| `/cancelar` | Cancela o agendamento atual    |

## 📋 Fluxo de agendamento

```
/start
  └── Menu principal
        ├── 📅 Agendar horário
        │     ├── Nome
        │     ├── Serviço (botões)
        │     ├── Data (DD/MM/AAAA)
        │     └── Horário (botões) → salva no Supabase ✅
        └── 🕐 Ver horários disponíveis
```

## 🛠 Estrutura do projeto

```
nail_bot/
├── bot.py                # Código principal
├── requirements.txt      # Dependências
├── .env.example          # Exemplo de variáveis de ambiente
└── supabase_schema.sql   # SQL para criar a tabela
```

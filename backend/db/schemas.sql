
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
        CREATE TYPE user_role AS ENUM ('CEO', 'PROJECT_MANAGER', 'assistant');
    ELSE
        BEGIN
            ALTER TYPE user_role ADD VALUE 'assistant';
        EXCEPTION WHEN duplicate_object THEN NULL; END;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'msg_role') THEN
        CREATE TYPE msg_role AS ENUM ('user', 'assistant', 'CEO', 'PROJECT_MANAGER');
    ELSE
        -- Ajout des nouveaux types si l'enum existe déjà
        BEGIN
            ALTER TYPE msg_role ADD VALUE 'CEO';
        EXCEPTION WHEN duplicate_object THEN NULL; END;
        BEGIN
            ALTER TYPE msg_role ADD VALUE 'PROJECT_MANAGER';
        EXCEPTION WHEN duplicate_object THEN NULL; END;
    END IF;
END $$;

-- 2. TABLE USERS (Gestion des accès)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE,
    hashed_password TEXT NOT NULL,
    role user_role NOT NULL DEFAULT 'PROJECT_MANAGER', -- CEO ou PM
    redmine_token TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index pour accélérer la connexion et les vérifications de rôle
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- 3. TABLE CONVERSATIONS
CREATE TABLE IF NOT EXISTS conversations (
    id VARCHAR(100) PRIMARY KEY,
    username VARCHAR(50) NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    role_user user_role,
    title VARCHAR(255),
    project_name VARCHAR(100), -- Le projet Redmine lié à cette discussion
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index pour retrouver vite les discussions d'un Manager
CREATE INDEX IF NOT EXISTS idx_conversations_username ON conversations(username);

-- 4. TABLE MESSAGES (Historique du Chat)
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(100) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    name_user VARCHAR(50) REFERENCES users(username) ON DELETE CASCADE,
    content TEXT NOT NULL,
    role msg_role DEFAULT 'user', -- user, assistant, CEO, PROJECT_MANAGER
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index pour charger l'historique de la conversation par ordre chronologique
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
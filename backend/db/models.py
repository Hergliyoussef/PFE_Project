from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from .session import Base
import enum

# 1. Définition des Enums (Parfait !)
class UserRole(str, enum.Enum):
    CEO = "CEO"
    PROJECT_MANAGER = "PROJECT_MANAGER"

class MsgRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"

# 2. Table Users
class User(Base):
    __tablename__ = "users"
    
    # NE PAS OUBLIER CETTE LIGNE :
    id = Column(Integer, primary_key=True, index=True) 
    
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(Text, nullable=False)
    role = Column(Enum(UserRole, name="user_role"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relation inverse pour SQLAlchemy
    conversations = relationship("Conversation", back_populates="owner")

# 3. Table Conversations
class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    title = Column(String(255))
    project_name = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

# 4. Table Messages
class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    role = Column(Enum(MsgRole, name="msg_role"), nullable=False) # Une seule fois suffit
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")
from sqlalchemy import Column, Integer, String, Text, Boolean, BigInteger, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class BotUser(Base):
    __tablename__ = 'bot_users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, nullable=False, unique=True)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    language_code = Column(String(10))
    is_bot = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)

    learner = relationship('Learner', back_populates='bot_user', uselist=False)

class Application(Base):
    __tablename__ = 'applications'

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    name = Column(Text)
    language = Column(Text)
    level = Column(Text)
    preferred_time = Column(Text)
    contact = Column(Text)

class Student(Base):
    __tablename__ = 'students'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    story = Column(Text, nullable=False)
    photo_file_id = Column(String)


class Learner(Base):
    __tablename__ = 'learners'

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_user_id = Column(Integer, ForeignKey('bot_users.id', ondelete='CASCADE'), nullable=False, unique=True)
    display_name = Column(String, nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False)

    bot_user = relationship('BotUser', back_populates='learner', lazy='joined')


class LessonReminder(Base):
    __tablename__ = 'lesson_reminders'

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_name = Column(String, nullable=False)
    chat_identifier = Column(String, nullable=False)
    is_recurring = Column(Boolean, nullable=False, default=True)
    days = Column(String)
    lesson_time = Column(String)
    lesson_datetime = Column(DateTime(timezone=True))
    lead_minutes = Column(Integer, nullable=False, default=60)
    next_run_at = Column(DateTime(timezone=True))
    last_notified_at = Column(DateTime(timezone=True))
    last_response = Column(String)
    last_response_at = Column(DateTime(timezone=True))
    last_decline_reason = Column(Text)
    comment = Column(Text)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

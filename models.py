import datetime
from app import database
from peewee import *


class BaseModel(Model):
    class Meta:
        database = database

class User(BaseModel):
    username = CharField(unique = True)
    password = CharField()
    email    = CharField(unique = True)
    join_at  = DateTimeField(default=datetime.datetime.now())

    def following(self):
        return(User.select()
                   .join(Relationship, on=Relationship.to_user)
                   .where(Relationship.from_user == self)
                   .order_by(User.username))

    def follower(self):
        return(User.select()
                   .join(Relationship, on=Relationship.from_user)
                   .where(Relationship.to_user == self)
                   .order_by(User.username))
                   
    def is_following(self, user):
        return (Relationship.select().where((Relationship.from_user == self)&
                (Relationship.to_user == user)).exists())

class Message(BaseModel):
    user          = ForeignKeyField(User, backref = 'messages')
    content       = TextField()
    published_at  = DateTimeField(default=datetime.datetime.now())

    def like(self):
        return(User.select()
                   .join(Likes, on=Likes.by_user)
                   .where(Likes.message == self)
                   .order_by(User.username))
                   
    def is_a_likers(self, user):
        return (Likes.select().where((Likes.message == self)&
        (Likes.by_user == user)).exists())


class Relationship(BaseModel):
    from_user = ForeignKeyField(User, backref = 'relationships')
    to_user   = ForeignKeyField(User, backref = 'related_to')

    class Meta:
        indexes = (
            (('from_user', 'to_user'), True),
        )


class Likes(BaseModel):
    message = ForeignKeyField(Message, backref='content_id')
    by_user = ForeignKeyField(User, backref='user')

    class Meta:
        indexes = (
            (('message', 'by_user'), True),
        )
from peewee import *

#db = MySQLDatabase('iNP', user='root', passwd='********')
#db = SqliteDatabase('database.db', pragmas={'foreign_keys': 1})
db = MySQLDatabase("test_0105", host=os.getenv('MySQL_RDS'), port=3306,
                   user=os.getenv('MySQL_USER'), passwd=os.getenv('MySQL_PASS'))

class BaseModel(Model):
    class Meta:
        database = db

class User(BaseModel):
    username = CharField(unique=True)
    password = CharField()


class Invitation(BaseModel):
    inviter = ForeignKeyField(User, on_delete='CASCADE')
    invitee = ForeignKeyField(User, on_delete='CASCADE')


class Friend(BaseModel):
    user = ForeignKeyField(User, on_delete='CASCADE')
    friend = ForeignKeyField(User, on_delete='CASCADE')


class Post(BaseModel):
    user = ForeignKeyField(User, on_delete='CASCADE')
    message = CharField()


class Follow(BaseModel):
    follower = ForeignKeyField(User, on_delete='CASCADE')
    followee = ForeignKeyField(User, on_delete='CASCADE')


class Token(BaseModel):
    token = CharField(unique=True)
    owner = ForeignKeyField(User, on_delete='CASCADE')

##################### New Tables #####################
class Group(BaseModel):
    group = CharField()
    user = ForeignKeyField(User, on_delete='CASCADE')

class App_Server(BaseModel):
    server = CharField()
    user = ForeignKeyField(User, on_delete='CASCADE')
#####################################################

if __name__ == '__main__':
    db.connect()
    db.create_tables([User, Invitation, Friend, Post, Follow, Token, Group, App_Server])



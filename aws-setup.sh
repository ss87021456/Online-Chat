#!/bin/bash
sudo apt-get update
sudo apt install -y python3-pip
pip3 install peewee
pip3 install stomp.py
pip3 install PyMySQL

sudo apt install -y default-jdk
cd /opt
sudo wget http://www.trieuvan.com/apache/activemq/5.15.8/apache-activemq-5.15.8-bin.tar.gz
sudo tar zxf apache-activemq-5.15.8-bin.tar.gz
sudo ln -s /opt/apache-activemq-5.15.8 activemq
sudo rm apache-activemq-5.15.8-bin.tar.gz
sudo /opt/activemq/bin/activemq start

cd /home/ubuntu/
cat > model.py << END
from peewee import *

db = MySQLDatabase("test_0105", host=os.getenv('MySQL_RDS'), port=3306, user=os.getenv('MySQL_USER'), passwd=os.getenv('MySQL_PASS'))

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

class Group(BaseModel):
    group = CharField()
    user = ForeignKeyField(User, on_delete='CASCADE')

class App_Server(BaseModel):
    server = CharField()
    user = ForeignKeyField(User, on_delete='CASCADE')

if __name__ == '__main__':
    db.connect()
    db.create_tables([User, Invitation, Friend, Post, Follow, Token, Group, App_Server])
END

cat > app_server.py << END
import os
import sys
import socket
from model import *
import json
import uuid
import stomp

class DBControl(object):
    def __auth(func):
        def validate_token(self, token=None, *args):
            if token:
                t = Token.get_or_none(Token.token == token)
                if t:
                    return func(self, t, *args)
            return {
                'status': 1,
                'message': 'Not login yet'
            }
        return validate_token

    @__auth
    def invite(self, token, username=None, *args):
        if not username or args:
            return {
                'status': 1,
                'message': 'Usage: invite <user> <id>'
            }
        if username == token.owner.username:
            return {
                'status': 1,
                'message': 'You cannot invite yourself'
            }
        friend = User.get_or_none(User.username == username)
        if friend:
            res1 = Friend.get_or_none((Friend.user == token.owner) & (Friend.friend == friend))
            res2 = Friend.get_or_none((Friend.friend == token.owner) & (Friend.user == friend))
            if res1 or res2:
                return {
                    'status': 1,
                    'message': '{} is already your friend'.format(username)
                }
            else:
                invite1 = Invitation.get_or_none((Invitation.inviter == token.owner) & (Invitation.invitee == friend))
                invite2 = Invitation.get_or_none((Invitation.inviter == friend) & (Invitation.invitee == token.owner))
                if invite1:
                    return {
                        'status': 1,
                        'message': 'Already invited'
                    }
                elif invite2:
                    return {
                        'status': 1,
                        'message': '{} has invited you'.format(username)
                    }
                else:
                    Invitation.create(inviter=token.owner, invitee=friend)
                    return {
                        'status': 0,
                        'message': 'Success!'
                    }
        else:
            return {
                'status': 1,
                'message': '{} does not exist'.format(username)
            }
        pass

    @__auth
    def list_invite(self, token, *args):
        if args:
            return {
                'status': 1,
                'message': 'Usage: list-invite <user>'
            }
        res = Invitation.select().where(Invitation.invitee == token.owner)
        invite = []
        for r in res:
            invite.append(r.inviter.username)
        return {
            'status': 0,
            'invite': invite
        }

    @__auth
    def accept_invite(self, token, username=None, *args):
        if not username or args:
            return {
                'status': 1,
                'message': 'Usage: accept-invite <user> <id>'
            }
        inviter = User.get_or_none(User.username == username)
        invite = Invitation.get_or_none((Invitation.inviter == inviter) & (Invitation.invitee == token.owner))
        if invite:
            Friend.create(user=token.owner, friend=inviter)
            invite.delete_instance()
            return {
                'status': 0,
                'message': 'Success!',
                'user': token.owner.username
            }
        else:
            return {
                'status': 1,
                'message': '{} did not invite you'.format(username)
            }
        pass

    @__auth
    def list_friend(self, token, *args):
        if args:
            return {
                'status': 1,
                'message': 'Usage: list-friend <user>'
            }
        friends = Friend.select().where((Friend.user == token.owner) | (Friend.friend == token.owner))
        res = []
        for f in friends:
            if f.user == token.owner:
                res.append(f.friend.username)
            else:
                res.append(f.user.username)
        return {
            'status': 0,
            'friend': res
        }

    @__auth
    def post(self, token, *args):
        if len(args) <= 0:
            return {
                'status': 1,
                'message': 'Usage: post <user> <message>'
            }
        Post.create(user=token.owner, message=' '.join(args))
        return {
            'status': 0,
            'message': 'Success!'
        }

    @__auth
    def receive_post(self, token, *args):
        if args:
            return {
                'status': 1,
                'message': 'Usage: receive-post <user>'
            }
        res = Post.select().where(Post.user != token.owner).join(Friend, on=((Post.user == Friend.user) | (Post.user == Friend.friend))).where((Friend.user == token.owner) | (Friend.friend == token.owner))
        post = []
        for r in res:
            post.append({
                'id': r.user.username,
                'message': r.message
            })
        return {
            'status': 0,
            'post': post
        }

    @__auth
    def send(self, token, username=None, *args):
        if len(args) <= 0: 
            return {
                'status': 1,
                'message': 'Usage: send <user> <friend> <message>'
            }

        friend = User.get_or_none(User.username == username)
        if not friend:
            return {
                'status': 1,
                'message': 'No such user exist'
            }

        check_friend = Friend.get_or_none((Friend.user == token.owner) & (Friend.friend == friend))
        check_friend_ = Friend.get_or_none((Friend.friend == token.owner) & (Friend.user == friend))
        if (not check_friend) and (not check_friend_):
            return {
                'status': 1,
                'message': '{} is not your friend'.format(username)
            }

        check_online = Token.get_or_none(Token.owner == friend)
        if not check_online:
            return {
                'status': 1,
                'message': '{} is not online'.format(username)
            }

        message=' '.join(args)
        conn = stomp.Connection([(os.getenv('ActiveMQ_Endpoint'), 61613)])
        conn.start()
        conn.connect()
        add_header = {'sender': token.owner.username, 'sendee':username, 'group':''}
        destination = '/queue/{}_2_{}'.format(token.owner.username, username)
        conn.send(destination, body=message, header=add_header)
        conn.disconnect()
        return {
            'status': 0,
            'message': 'Success!'
        }

    @__auth
    def create_group(self, token, groupname=None, *args):
        if len(args) > 0 or groupname == None: 
            return {
                'status': 1,
                'message': 'Usage: create-group <user> <group>'
            }

        check_group = Group.get_or_none(Group.group == groupname)
        if check_group:
            return {
                'status': 1,
                'message': '{} already exist'.format(groupname)
            }

        Group.create(user=token.owner, group=groupname)
        return {
            'status': 0,
            'message': 'Success!'
        }

    @__auth
    def list_group(self, token, *args):
        if len(args) > 0: 
            return {
                'status': 1,
                'message': 'Usage: list-group <user>'
            }

        groups_info = []
        groups = Group.select(Group.group).distinct()
        for group in groups:
            groups_info.append(group.group)
            print(group.group)
        return {
            'status': 0,
            'groups': groups_info
        }

    @__auth
    def list_joined(self, token, *args):
        if len(args) > 0: 
            return {
                'status': 1,
                'message': 'Usage: list-joined <user>'
            }
        groups_info = []
        groups = Group.select().where(Group.user == token.owner)
        for group in groups:
            groups_info.append(group.group)
            print(group.group)
        return {
            'status': 0,
            'groups': groups_info
        }

    @__auth
    def join_group(self, token, groupname=None, *args):
        if len(args) > 0: 
            return {
                'status': 1,
                'message': 'Usage: join-group <user> <group>'
            }

        groups = Group.select().where(Group.group == groupname)
        if not groups:
            return {
                'status': 1,
                'message': '{} does not exist'.format(groupname)
            }

        groups = Group.select().where(Group.user == token.owner)
        for group in groups:
            if group.group == groupname:
                return {
                    'status': 1,
                    'message': 'Already a member of {}'.format(groupname)
                }

        Group.create(user=token.owner, group=groupname)
        return {
            'status': 0,
            'message': 'Success!'
        }

    @__auth
    def send_group(self, token, groupname=None, *args):
        if len(args) <= 0: 
            return {
                'status': 1,
                'message': 'Usage: send-group <user> <group> <message>'
            }

        check_group = Group.get_or_none(Group.group == groupname)
        if not check_group:
            return {
                'status': 1,
                'message': 'No such group exist'
            }

        check_user_in_group = Group.select().where((Group.user == token.owner) & (Group.group == groupname))
        #print(token.owner.username)
        #print(check_user_in_group[0].user.username, check_user_in_group[0].group)
        if not check_user_in_group:
            return {
                'status': 1,
                'message': 'You are not the member of {}'.format(groupname)
            }

        message=' '.join(args)
        conn = stomp.Connection([(os.getenv('ActiveMQ_Endpoint'), 61613)])
        conn.start()
        conn.connect()
        add_header = {'sender': token.owner.username, 'sendee':'', 'group':groupname}
        destination = '/topic/{}'.format(groupname)
        conn.send(destination, body=message, header=add_header)
        conn.disconnect()
        return {
            'status': 0,
            'message': 'Success!'
        }

class Server(object):
    def __init__(self, ip, port):
        try:
            socket.inet_aton(ip)
            if 0 < int(port) < 65535:
                self.ip = ip
                self.port = int(port)
            else:
                raise Exception('Port value should between 1~65535')
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.db = DBControl()
        except Exception as e:
            print(e, file=sys.stderr)
            sys.exit(1)

    def run(self):
        self.sock.bind((self.ip, self.port))
        self.sock.listen(100)
        socket.setdefaulttimeout(0.1)
        while True:
            try:
                conn, addr = self.sock.accept()
                with conn:
                    cmd = conn.recv(4096).decode()
                    resp = self.__process_command(cmd)
                    conn.send(resp.encode())
            except Exception as e:
                print(e, file=sys.stderr)

    def __process_command(self, cmd):
        command = cmd.split()
        if len(command) > 0:
            command_exec = getattr(self.db, command[0].replace('-', '_'), None)
            print(command[0].replace('-', '_'))
            if command_exec:
                return json.dumps(command_exec(*command[1:]))
        return self.__command_not_found(command[0])

    def __command_not_found(self, cmd):
        return json.dumps({
            'status': 1,
            'message': 'Unknown command {}'.format(cmd)
        })

def launch_server(ip, port):
    c = Server(ip, port)
    c.run()

if __name__ == '__main__':
    if sys.argv[1] and sys.argv[2]:
        launch_server(sys.argv[1], sys.argv[2])
END
python3 app_server.py 0.0.0.0 8888

import sys
import socket
from model import *
import json
import uuid
import stomp
from create_aws import launch_app_server, terminate_app_server


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

    def register(self, username=None, password=None, *args):
        if not username or not password or args:
            return {
                'status': 1,
                'message': 'Usage: register <username> <password>'
            }
        if User.get_or_none(User.username == username):
            return {
                'status': 1,
                'message': '{} is already used'.format(username)
            }
        
        res = User.create(username=username, password=password)
        if res:
            return {
                'status': 0,
                'message': 'Success!'
            }
        else:
            return {
                'status': 1,
                'message': 'Register failed due to unknown reason'
            }

    @__auth
    def delete(self, token, *args):
        if args:
            return {
                'status': 1,
                'message': 'Usage: delete <user>'
            }
        token.owner.delete_instance()
        return {
            'status': 0,
            'message': 'Success!'
        }

    def login(self, username=None, password=None, *args):
        if not username or not password or args:
            return {
                'status': 1,
                'message': 'Usage: login <id> <password>'
            }
        res = User.get_or_none((User.username == username) & (User.password == password))
        if res:
            #### friend information for client to subscribe ####
            friends = Friend.select().where((Friend.user == res) | (Friend.friend == res))
            friends_info = []
            for f in friends:
                if f.user == res:
                    friends_info.append(f.friend.username)
                    print("===DEBUG friend===:", f.friend.username)
                else:
                    friends_info.append(f.user.username)
                    print("===DEBUG friend===:", f.user.username)
            ####################################################

            #### group information for client to subscribe ####
            groups = Group.select().where(Group.user == res)
            groups_info = []
            for group in groups:
                print("===DEBUG group===:", group.group)
                groups_info.append(group.group)
            ####################################################

            t = Token.get_or_none(Token.owner == res)
            wait_signal = 0

            if not t: # means originally offline
                t = Token.create(token=str(uuid.uuid4()), owner=res)
                # check whether there's sufficient app server
                print("[DEBUG] originally offline")
                server_num = App_Server.select(App_Server.server).distinct()
                print("[DEBUG] server_num:", server_num.count())
                
                USER_LIMIT = 5
                free_servers = App_Server.select(App_Server.server).group_by(App_Server.server).having(fn.COUNT(App_Server.server) < USER_LIMIT)

                if free_servers:
                    for ser in free_servers:
                        print("free server {}".format(ser.server))
                    print("[DEBUG] contains free server, choose first one {}".format(free_servers[0].server))
                    App_Server.create(user=t.owner, server=free_servers[0].server)
                    app_server_ip = free_servers[0].server

                else:
                    print("There's no free server need to launch new!!")
                    wait_signal = 1
                    app_server_ip = launch_app_server()
                    App_Server.create(user=t.owner, server=app_server_ip)
                print("[DEBUG] originally offline done")

            else: # means already login then get its app server
                print("[DEBUG] already login then get its app server")
                app_server_ip = App_Server.get_or_none(App_Server.user == res)
                app_server_ip = app_server_ip.server
                print("[DEBUG] already login then get its app server done")

            return {
                'status': 0,
                'token': t.token,
                'message': 'Success!',
                'friends': friends_info,
                'groups': groups_info,
                'app_server_ip' : app_server_ip,
                'wait_signal' : wait_signal
            }
        else:
            return {
                'status': 1,
                'message': 'No such user or password error'
            }

    @__auth
    def logout(self, token, *args):
        if args:
            return {
                'status': 1,
                'message': 'Usage: logout <user>'
            }
        user = App_Server.get_or_none(App_Server.user == token.owner)
        public_ip = user.server
        check_remain = App_Server.select().where(App_Server.server == public_ip).count()
        if check_remain == 1:
            terminate_app_server(ip_address=public_ip)

        user.delete_instance()
        token.delete_instance()

        return {
            'status': 0,
            'message': 'Bye!'
        }

    ########## below is for handling accidental using login server #########
    @__auth
    def invite(self, token, username=None, *args):
        pass
    
    @__auth
    def list_invite(self, token, *args):
        pass
    
    @__auth
    def accept_invite(self, token, username=None, *args):
        pass

    @__auth
    def list_friend(self, token, *args):
        pass
    
    @__auth
    def post(self, token, *args):
        pass

    @__auth
    def receive_post(self, token, *args):
        pass

    @__auth
    def send(self, token, username=None, *args):
        pass

    @__auth
    def create_group(self, token, groupname=None, *args):
        pass

    @__auth
    def list_group(self, token, *args):
        pass

    @__auth 
    def list_joined(self, token, *args):
        pass

    @__auth
    def join_group(self, token, groupname=None, *args):
        pass

    @__auth 
    def send_group(self, token, groupname=None, *args):
        pass
    #####################################################################

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
            # getattr(x, 'foobar') is equivalent to x.foobar
            command_exec = getattr(self.db, command[0].replace('-', '_'), None)
            print(command[0].replace('-', '_'))
            if command_exec:
                # *command[1:] 會將1:這個list用iteration的方式一個一個當做argument傳進去
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


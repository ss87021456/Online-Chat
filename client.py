import sys
import socket
import json
import os
from stomp import * 
import stomp
import time

class ClientListener(object):
    def on_message(self, headers, msg):
        send_info = headers['header']
        send_info = send_info.replace("\'", "\"") # otherwise cannot use json load
        send_info = json.loads(send_info)
        if send_info['group']:
            output = "<<<{}->GROUP<{}>: {}>>>".format(send_info['sender'], send_info['group'], msg)
        else:
            output = "<<<{}->{}: {}>>>".format(send_info['sender'], send_info['sendee'], msg)

        #print("====DEBUG====", output)
        print(output)

class Client(object):
    def __init__(self, ip, port):
        try:
            socket.inet_aton(ip)
            if 0 < int(port) < 65535:
                self.ip = ip
                self.port = int(port)
            else:
                raise Exception('Port value should between 1~65535')
            self.cookie = {}
            self.activemq = {}
            self.listener = {}
            self.client_2_server = {}
        except Exception as e:
            print(e, file=sys.stderr)
            sys.exit(1)

        #self.conn = conn

    def run(self):
        while True:
            cmd = sys.stdin.readline()
            if cmd == 'exit' + os.linesep:
                return
            if cmd != os.linesep:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        if cmd.split()[0] in ['register', 'login', 'logout', 'delete']:
                            s.connect((self.ip, self.port))
                            #print("[DEBUG] connect to login server {}:{}".format(self.ip, self.port))
                        else:
                            try:
                                app_server_ip = self.client_2_server[cmd.split()[1]]
                            except:
                                app_server_ip = self.ip
                            s.connect((app_server_ip, 8888)) # predefined default app server port to 8888
                            #print("[DEBUG] connect to app server {}:{}".format(app_server_ip, 8888))
                            
                        cmd = self.__attach_token(cmd)
                        s.send(cmd.encode())
                        resp = s.recv(4096).decode()
                        self.__show_result(json.loads(resp), cmd)
                except Exception as e:
                    print(e, file=sys.stderr)

    def __show_result(self, resp, cmd=None):
        if 'message' in resp:
            print(resp['message'])

        if 'invite' in resp:
            if len(resp['invite']) > 0:
                for l in resp['invite']:
                    print(l)
            else:
                print('No invitations')

        if 'friend' in resp:
            if len(resp['friend']) > 0:
                for l in resp['friend']:
                    print(l)
            else:
                print('No friends')

        if 'post' in resp:
            if len(resp['post']) > 0:
                for p in resp['post']:
                    print('{}: {}'.format(p['id'], p['message']))
            else:
                print('No posts')

        if 'app_server_ip' in resp:
            pass
            #print(resp['app_server_ip'])


        ###################### All modified in here ######################
        if cmd:
            command = cmd.split()
            if resp['status'] == 0 and command[0] == 'login': # success login
                if 'wait_signal' in resp:
                    #print(resp['wait_signal'])
                    if resp['wait_signal'] == 1:
                        print("[DEBUG] need to wait 2 min for launching app server..")
                        time.sleep(120)

                username = command[1]
                token = resp['token']

                self.cookie[command[1]] = token
                self.client_2_server[command[1]] = resp['app_server_ip']

                self.activemq[token] = stomp.Connection(
                    [(os.getenv('ActiveMQ_Endpoint'), 61613)])
                self.activemq[token].set_listener(token, ClientListener())
                self.activemq[token].start()
                self.activemq[token].connect()

                # need to subscribe your friend (personal channel)
                if resp['friends']:
                    for friend in resp['friends']:
                        friend2user = friend + '_2_' + username
                        #print("====DEBUG==== personal channel create:", friend2user)
                        destination = '/queue/'+friend2user
                        self.activemq[token].subscribe(destination, id=token)

                # need to subscribe your group (group channel)
                if resp['groups']:
                    for group in resp['groups']:
                        #print("====DEBUG==== {} subscribe to topic {}".format(token, group))
                        destination = '/topic/'+ group
                        self.activemq[token].subscribe(destination, id=token)

            # success logout or delete, need to unsubscribe
            elif resp['status'] == 0 and (command[0] == 'logout' or command[0] == 'delete'): 
                token = command[1]
                self.activemq[token].unsubscribe(id=token)
                self.activemq[token].disconnect()

            elif resp['status'] == 0 and command[0] == 'accept-invite': # success accept-invite
                # need to subscribe personal channel
                token = command[1]
                friend = command[2]
                username = resp['user']
                friend2user = friend + '_2_' + username
                destination = '/queue/'+friend2user
                self.activemq[token].subscribe(destination, id=token)
                #print("====DEBUG==== personal channel created", friend2user)

                # help friend to subscribe too
                friend_token = self.cookie[friend]
                user2friend = username + '_2_' + friend
                destination = '/queue/'+user2friend
                self.activemq[friend_token].subscribe(destination, id=friend_token)
                #print("====DEBUG==== personal channel created", user2friend)


            elif resp['status'] == 0 and command[0] == 'create-group': # success create-group
                # need to subscribe user itself into that group
                #print("====DEBUG==== group channel created {}".format(command[2]))
                destination = '/topic/'+ command[2]
                token = command[1]
                self.activemq[token].subscribe(destination, id=token)
                #print("====DEBUG==== token {} subscribe to topic {}".format(token, command[2]))

            elif resp['status'] == 0 and command[0] == 'list-group':
                if len(resp['groups']) > 0:
                    for l in resp['groups']:
                        print(l)
                else:
                    print('No groups')
            
            elif resp['status'] == 0 and command[0] == 'list-joined': # success list-joined
                if len(resp['groups']) > 0:
                    for l in resp['groups']:
                        print(l)
                else:
                    print('No groups')
            
            elif resp['status'] == 0 and command[0] == 'join-group': # success join-group
                # need to subscribe user itself into that group
                destination = '/topic/'+ command[2]
                token = command[1]
                self.activemq[token].subscribe(destination, id=token)
                #print("====DEBUG==== token {} subscribe to topic {}".format(token, command[2]))

            # success send and send-group, idle
            elif resp['status'] == 0 and (command[0] == 'send' or command[0] == 'send-group'):
                pass



    def __attach_token(self, cmd=None):
        if cmd:
            command = cmd.split()
            if len(command) > 1:
                if command[0] != 'register' and command[0] != 'login':
                    if command[1] in self.cookie:
                        command[1] = self.cookie[command[1]]
                    else:
                        command.pop(1)
            return ' '.join(command)
        else:
            return cmd


def launch_client(ip, port):
    c = Client(ip, port)
    c.run()

if __name__ == '__main__':
    if len(sys.argv) == 3:
        launch_client(sys.argv[1], sys.argv[2])
    else:
        print('Usage: python3 {} IP PORT'.format(sys.argv[0]))


# Online-Chat
<img src="Example%20architecture.png" width="500">
- This is a chat room service with distributed server architecture, using ActiveMQ as real-time messaging server.
- Implemented auto scaling with script and Python SDK boto3 to manage application server on AWS EC2.
- Maintained user and chat data using MySQL on AWS RDS, and query with peewee object-relational mapper(ORM).

### local client requirement:
- client.py - for user to login

### login server requirement:
- login_server.py - handle [register|login|logout|delete] and aws [create|terminate]
- model.py - for defining and creating database
- create_aws.py - implementation of creating, terminating aws EC2
- aws-setup.py - initial script for seting up a application server

### application server requirement: [in fact, login server handle all the setup]
- app_server.py - handle all the other command sent by client
- model.py - database usage

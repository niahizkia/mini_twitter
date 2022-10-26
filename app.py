import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from peewee import *
from hashlib import md5


app = Flask(__name__)
app.secret_key = 'jdfjnviuhd87432fdjkfa.kjfj'


DATABASE = 'tweets.db'
database = SqliteDatabase(DATABASE)

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

    def followers(self):
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



class Relationship(BaseModel):
    from_user = ForeignKeyField(User, backref = 'relationships')
    to_user   = ForeignKeyField(User, backref = 'related_to')

    class Meta:
        indexes = (
            (('from_user', 'to_user'), True),
        )


@app.before_request
def before_request():
    database.connect()

@app.after_request
def after_request(response):
    database.close()
    return response


def create_tables():
    with database:
        database.create_tables([User, Relationship, Message])





# ==========================================================================================
# ========= HELPER FUNCTION ================================================================
# ==========================================================================================

def auth_user(user):
    session['logged_in'] = True
    session['user_id'] = user.id
    session['username'] = user.username
    flash('Login success as '+ session['username'])

def get_current_user():
    if session.get('logged_in'):
        return User.get(User.id == session['user_id'])



def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def login_fulfill(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('logged_in'):
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function


    
@app.context_processor
def _inject_user():
    return{'active_user': get_current_user()}


# ==========================================================================================
# ========= ROOTING AUTHENTICATION =========================================================
# ==========================================================================================

@app.route('/')
@login_required
def home():
    user = get_current_user()
    messages = (Message.select()
                        .where((Message.user << user.following()) | 
                                (Message.user))
                        .order_by(Message.published_at.desc())
    )
    return render_template('index.html', messages=messages)


@app.route('/register', methods=['GET', 'POST'])
@login_fulfill
def register():
    if request.method == 'POST' and request.form['username']:
        try:
            with database.atomic():
                user = User.create(
                    username = request.form['username'],
                    password = md5(request.form['password'].encode('utf-8')).hexdigest(),
                    email    = request.form['email']
                )
            auth_user(user)
            return redirect(url_for('home'))

        except IntegrityError:
            flash('Username already exist')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
@login_fulfill
def login():
    if request.method == 'POST' and request.form['username']:
        try:
            hashed_pass = md5(request.form['password'].encode('utf-8')).hexdigest(),
            user        = User.get(
                            (User.username == request.form['username']) &
                            (User.password == hashed_pass))
        except User.DoesNotExist:
            flash('Username or password is wrong!')

        else:
            auth_user(user)
            # current_user = get_current_user()
            # return current_user.username
            return redirect(url_for('home'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('Log out success..')
    return redirect(url_for('home'))




# ==========================================================================================
# ========= ROOTING TWEET ==================================================================
# ==========================================================================================

@app.route('/new', methods=['GET', 'POST'])
@login_required
def new_tweet():
    user = get_current_user()
    if request.method == 'POST' and request.form['content']:
        message = Message.create(
            user    = user,
            content = request.form['content']
        )

        flash('status updated..')
        return redirect(url_for('user_profile', username = user.username))
    return render_template('new_tweet.html')


@app.route('/user/<username>')
def user_profile(username):
    try:
        user = User.get(User.username == username)
    except User.DoesNotExist:
        abort(404)
    messages = user.messages.order_by(Message.published_at.desc())
    return render_template('profile.html', messages=messages, user=user)


@app.route('/user_follow/<username>', methods=['POST'])
def user_follow(username):
    try:
        user = User.get(User.username == username)
    except User.DoesNotExist:
        abort(404)
    
    try:
        with database.atomic():
            Relationship.create(
                from_user = get_current_user(),
                to_user = user,
            )
    except IntegrityError:
        pass
    flash('You are following '+ username +' now')
    return redirect(url_for('user_profile', username=username))


@app.route('/user_unfollow/<username>', methods=['POST'])
def user_unfollow(username):
    try:
        user = User.get(User.username == username)
    except User.DoesNotExist:
        abort(404)
    
    (Relationship.delete()
        .where(
            (Relationship.from_user == get_current_user()) &
            (Relationship.to_user == user))
            .execute())

    flash('You are unfollowing '+ username +' now')
    return redirect(url_for('user_profile', username=username))


# End of the line
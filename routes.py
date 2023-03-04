import datetime

from app import app, database
from functools import wraps
from flask import render_template, request, redirect, url_for, session, flash, abort, jsonify, make_response
from models import User, Relationship, Message, Likes
from peewee import IntegrityError
from hashlib import md5



@app.before_request
def before_request():
    database.connect()

@app.after_request
def after_request(response):
    database.close()
    return response




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


def getUserOrAbort(username):
    try:
        return User.get(User.username == username)
    except User.DoesNotExist:
        abort(404)

def getStatusOrAbort(id):
    try:
        return Message.get(Message.id == id)
    except User.DoesNotExist:
        abort(404)
    
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
                                (Message.user == user.id))
                        .order_by(Message.published_at.desc()).limit(5)
    )
    return render_template('index.html', messages=messages, user=user)

@app.route('/loadMore/<int:pageNum>')
def loadMore(pageNum):
    user = get_current_user()
    messages = {}
    for message in (Message.select()
                        .where((Message.user << user.following()) | 
                                (Message.user == user.id))
                        .order_by(Message.published_at.desc())
                        .paginate(pageNum, 5)):
        total_like = len(message.like())
        liker = message.is_a_likers(user=user)
        print(liker)
        print(message.id)
        print(total_like)
        messages[message.id] = {
            'content'   : message.content,
            'username'  : message.user.username,
            'time'      : message.published_at,
            'id'        : message.id,
            'like'      : total_like,
            'liker'     : liker
        }

    return jsonify(messages)


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
            content = request.form['content'],
            published_at = datetime.datetime.now()
        )

        flash('status updated..')
        return redirect(url_for('user_profile', username = user.username))
    return render_template('new_tweet.html')


@app.route('/user/<username>')
def user_profile(username):
    user = getUserOrAbort(username)
    messages = user.messages.order_by(Message.published_at.desc())
    return render_template('profile.html', messages=messages, user=user)


@app.route('/user_follow/<username>', methods=['POST'])
def user_follow(username):
    user = getUserOrAbort(username)
    
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
    user = getUserOrAbort(username)
    
    (Relationship.delete()
        .where(
            (Relationship.from_user == get_current_user()) &
            (Relationship.to_user == user))
            .execute())

    flash('You are unfollowing '+ username +' now')
    return redirect(url_for('user_profile', username=username))


@app.route('/user/<username>/following')
def show_following(username):
    user = getUserOrAbort(username)
    return render_template('user_list.html', users = user.following())



@app.route('/user/<username>/follower')
def show_follower(username):
    user = getUserOrAbort(username)
    return render_template('user_list.html', users = user.follower())



@app.route('/like/<content>', methods=['POST'])
def like(content):
    content = getStatusOrAbort(content)

    try:
        with database.atomic():
            Likes.create(
                message = content,
                by_user = get_current_user(),
            )
    except IntegrityError:
        pass
    return redirect(url_for('home'))


@app.route('/dislike/<content>', methods=['POST'])
def dislike(content):
    content = getStatusOrAbort(content)
    
    (Likes.delete()
        .where(
            (Likes.by_user == get_current_user()) &
            (Likes.message == content))
            .execute())

    return redirect(url_for('home'))

# End of the line
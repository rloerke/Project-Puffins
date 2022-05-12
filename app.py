import os
from werkzeug.security import generate_password_hash, check_password_hash
from sqlite3 import dbapi2 as sqlite3
from flask import Flask, request, session, g, redirect, url_for, render_template, flash

# Create the application
app = Flask(__name__)

# Load default config and override config from an environment variable
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'puffins.db'),
    DEBUG=True,
    SECRET_KEY='development key',
))
app.config.from_envvar('PUFFINS_SETTINGS', silent=True)


def connect_db():
    # Connects to the specific database.
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv


def init_db():
    # Initializes the database.
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()


@app.cli.command('initdb')
def initdb_command():
    # Creates the database tables.
    init_db()
    print('Initialized the database.')


def get_db():
    # Opens a new database connection if there is none yet for the current application context.
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db


@app.teardown_appcontext
def close_db(error):
    # Closes the database again at the end of the request.
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()


@app.route('/', methods=['GET'])
def show_entries():
    # Displays the posts currently in the database
    db = get_db()
    filter_it = request.args.get('filter')
    if filter_it == "" or filter_it is None:
        cur = db.execute('SELECT *, COUNT(comments.linked_post) AS post_count, '
                         'SUM(likes.tVote) as vote_total FROM posts '
                         'LEFT JOIN comments ON posts.postID = comments.linked_post '
                         'JOIN users ON users.userID = posts.posterID '
                         'LEFT JOIN likes ON likes.likedPostID = posts.postID '
                         'WHERE posts.tooPopular = 0 and '
                         'NOT EXISTS (SELECT blockedUsername FROM blockedUsers '
                         'WHERE blockedUsers.blockedUsername = users.userName) '
                         'GROUP BY posts.postID ORDER BY postID DESC')
    else:
        cur = db.execute('SELECT *, COUNT(comments.linked_post) AS post_count, '
                         'SUM(likes.tVote) as vote_total FROM posts '
                         'LEFT JOIN comments ON posts.postID = comments.linked_post '
                         'JOIN users ON users.userID = posts.posterID '
                         'LEFT JOIN likes ON likes.likedPostID = posts.postID '
                         'WHERE category LIKE ? AND posts.tooPopular = 0 and '
                         'NOT EXISTS (SELECT blockedUsername FROM blockedUsers '
                         'WHERE blockedUsers.blockedUsername = users.userName) '
                         'GROUP BY posts.postID ORDER BY postID DESC', [filter_it])
        flash("Filtered Unpopular Opinions based on Desired Category")
    posts = cur.fetchall()
    curr = db.execute('SELECT DISTINCT category FROM posts WHERE posts.tooPopular = 0 ORDER BY category ASC')
    categories = curr.fetchall()
    return render_template('show_posts.html', posts=posts, categories=categories, user=load_user())


@app.route('/upVote', methods=['POST'])
def upvote():
    # Allow  users to upvote a post
    user = load_user()
    db = get_db()
    posted_id = request.form["postID"]
    cur = db.execute('SELECT * FROM likes WHERE likedPostID = ? AND likingUserID = ?',
                     [posted_id, user['userID']])
    repeat = cur.fetchone()
    if (repeat is None) or (user['userName'] == 'admin'):
        if user is not None:
            db.execute('INSERT INTO likes (likingUserID, likedPostID, tVote) VALUES (?, ?, ?)',
                       [user['userID'], posted_id, 1])
            db.commit()
            vote_total = db.execute('SELECT *, SUM(likes.tVote) AS vote_count FROM likes WHERE likedPostID = ?',
                                    [posted_id]).fetchone()
            if vote_total['vote_count'] > 20:
                db.execute('UPDATE posts SET tooPopular = 1 WHERE postID = ?', [posted_id])
                db.commit()
                flash('Your vote has made this post too popular! It has been moved to the Too Popular Posts section.')
                return redirect(url_for('popular'))
            else:
                return redirect(url_for('show_entries'))
        else:
            flash('Your must be logged in to vote!')
            return redirect(request.referrer)
    elif repeat['tVote'] == -1:
        db.execute("UPDATE likes SET tVote = ? WHERE likingUserID = ? and likedPostID = ?",
                   [1, user['userID'], posted_id])
        db.commit()
        return redirect(url_for('show_entries'))
    else:
        flash('You have already voted')
        return redirect(url_for('show_entries'))


@app.route('/downVote', methods=['POST'])
def downvote():
    # Allow  users to downvote a post
    user = load_user()
    db = get_db()
    posted_id = request.form["postID"]
    cur = db.execute('SELECT * FROM likes WHERE likedPostID = ? AND likingUserID = ?',
                     [posted_id, user['userID']])
    repeat = cur.fetchone()
    if (repeat is None) or (user['userName'] == 'admin'):
        if user is not None:
            db.execute('INSERT INTO likes (likingUserID, likedPostID, tVote) VALUES (?, ?, ?)',
                       [user['userID'], posted_id, -1])
            db.commit()
            return redirect(url_for('show_entries'))
        else:
            flash('Your must be logged in to vote!')
            return redirect(request.referrer)
    elif repeat['tVote'] == 1:
        db.execute("UPDATE likes SET tVote = ? WHERE likingUserID = ? and likedPostID = ?",
                   [-1, user['userID'], posted_id])
        db.commit()
        return redirect(url_for('show_entries'))
    else:
        flash('You have already voted')
        return redirect(url_for('show_entries'))


@app.route('/react_laugh', methods=['POST'])
def react_laugh():
    # Allows user to react to a post
    user = load_user()
    db = get_db()
    posted_id = request.form["postID"]
    cur = db.execute('SELECT * FROM reactions WHERE likedPostID = ? AND likingUserID = ?',
                     [posted_id, user['userID']])
    repeat = cur.fetchone()
    if (repeat is None) or (user['userName'] == 'admin'):
        if user is not None:
            db.execute('INSERT INTO reactions (likingUserID, likedPostID, tVote) VALUES (?, ?, ?)',
                       [user['userID'], posted_id, 1])
            db.commit()
            db.execute("UPDATE posts SET laughScore = (laughScore + 1) WHERE postID = ?",
                       [posted_id])
            db.commit()
            return redirect(url_for('show_entries'))
        else:
            return redirect(url_for('login'))
    elif repeat['tVote'] == 2:
        db.execute("UPDATE posts SET sadScore = (sadScore - 1) WHERE postID = ?",
                   [posted_id])
        db.commit()
        db.execute("UPDATE posts SET laughScore = (laughScore + 1) WHERE postID = ?",
                   [posted_id])
        db.commit()
        db.execute("UPDATE reactions SET tVote = ? WHERE likingUserID = ? AND likedPostID = ?",
                   [1, user['userID'], posted_id])
        db.commit()
        return redirect(url_for('show_entries'))

    elif repeat['tVote'] == 3:
        db.execute("UPDATE posts SET angryScore = (angryScore - 1) WHERE postID = ?",
                   [posted_id])
        db.commit()
        db.execute("UPDATE posts SET laughScore = (laughScore + 1) WHERE postID = ?",
                   [posted_id])
        db.commit()
        db.execute("UPDATE reactions SET tVote = ? WHERE likingUserID = ? AND likedPostID = ?",
                   [1, user['userID'], posted_id])
        db.commit()
        return redirect(url_for('show_entries'))

    else:
        flash('You have already reacted')
        return redirect(url_for('show_entries'))


@app.route('/react_sad', methods=['POST'])
def react_sad():
    # Allows user to react to a post
    user = load_user()
    db = get_db()
    posted_id = request.form["postID"]
    cur = db.execute('SELECT * FROM reactions WHERE likedPostID = ? AND likingUserID = ?',
                     [posted_id, user['userID']])
    repeat = cur.fetchone()
    if (repeat is None) or (user['userName'] == 'admin'):
        if user is not None:
            db.execute('INSERT INTO reactions (likingUserID, likedPostID, tVote) VALUES (?, ?, ?)',
                       [user['userID'], posted_id, 2])
            db.commit()
            db.execute("UPDATE posts SET sadScore = (sadScore + 1) WHERE postID = ?",
                       [posted_id])
            db.commit()
            return redirect(url_for('show_entries'))
        else:
            return redirect(url_for('login'))

    elif repeat['tVote'] == 1:
        db.execute("UPDATE posts SET laughScore = (laughScore - 1) WHERE postID = ?",
                   [posted_id])
        db.commit()
        db.execute("UPDATE posts SET sadScore = (sadScore + 1) WHERE postID = ?",
                   [posted_id])
        db.commit()
        db.execute("UPDATE reactions SET tVote = ? WHERE likingUserID = ? AND likedPostID = ?",
                   [2, user['userID'], posted_id])
        db.commit()
        return redirect(url_for('show_entries'))

    elif repeat['tVote'] == 3:
        db.execute("UPDATE posts SET angryScore = (angryScore - 1) WHERE postID = ?",
                   [posted_id])
        db.commit()
        db.execute("UPDATE posts SET sadScore = (sadScore + 1) WHERE postID = ?",
                   [posted_id])
        db.commit()
        db.execute("UPDATE reactions SET tVote = ? WHERE likingUserID = ? AND likedPostID = ?",
                   [2, user['userID'], posted_id])
        db.commit()
        return redirect(url_for('show_entries'))
    else:
        flash('You have already reacted')
        return redirect(url_for('show_entries'))


@app.route('/react_angry', methods=['POST'])
def react_angry():
    # Allows user to react to a post
    user = load_user()
    db = get_db()
    posted_id = request.form["postID"]
    cur = db.execute('SELECT * FROM reactions WHERE likedPostID = ? AND likingUserID = ?',
                     [posted_id, user['userID']])
    repeat = cur.fetchone()
    if (repeat is None) or (user['userName'] == 'admin'):
        if user is not None:
            db.execute('INSERT INTO reactions (likingUserID, likedPostID, tVote) VALUES (?, ?, ?)',
                       [user['userID'], posted_id, 3])
            db.commit()
            db.execute("UPDATE posts SET angryScore = (angryScore + 1) WHERE postID = ?",
                       [posted_id])
            db.commit()
            return redirect(url_for('show_entries'))
        else:
            return redirect(url_for('login'))
    elif repeat['tVote'] == 1:
        db.execute("UPDATE posts SET laughScore = (laughScore - 1) WHERE postID = ?",
                   [posted_id])
        db.commit()
        db.execute("UPDATE posts SET angryScore = (angryScore + 1) WHERE postID = ?",
                   [posted_id])
        db.commit()
        db.execute("UPDATE reactions SET tVote = ? WHERE likingUserID = ? AND likedPostID = ?",
                   [3, user['userID'], posted_id])
        db.commit()
        return redirect(url_for('show_entries'))

    elif repeat['tVote'] == 2:
        db.execute("UPDATE posts SET sadScore = (sadScore - 1) WHERE postID = ?",
                   [posted_id])
        db.commit()
        db.execute("UPDATE posts SET angryScore = (angryScore + 1) WHERE postID = ?",
                   [posted_id])
        db.commit()
        db.execute("UPDATE reactions SET tVote = ? WHERE likingUserID = ? AND likedPostID = ?",
                   [3, user['userID'], posted_id])
        db.commit()
        return redirect(url_for('show_entries'))
    else:
        flash('You have already reacted')
        return redirect(url_for('show_entries'))


@app.route('/view', methods=['GET', 'POST'])
def show_single_post():
    # Displays a single post and its comments
    id_post = request.args['postID']
    db = get_db()
    cur = db.execute('SELECT pTitle, postID, category, text_body, posterID, userID, userName, rank FROM posts '
                     'JOIN users ON posts.posterID = users.userID WHERE postID=? AND posts.tooPopular = 0', [id_post])
    post = cur.fetchall()
    curr = db.execute('SELECT userName, comment_body, userID, authorID, linked_post FROM comments '
                      'JOIN users ON comments.authorID = users.userID WHERE linked_post=?', [id_post])
    comments = curr.fetchall()
    com = db.execute('SELECT COUNT(*) FROM comments WHERE linked_post=?', [id_post])
    num_comments = com.fetchall()[0]
    likes = db.execute('SELECT SUM(likes.tVote) AS vote_total FROM likes WHERE likedPostID = ?',
                       [id_post]).fetchall()[0]
    return render_template('single_post_view.html', post=post, comments=comments,
                           num_comments=num_comments, user=load_user(), likes=likes)


@app.route('/comment', methods=['GET'])
def make_comment():
    # Redirects to a form for writing comments
    id_post = request.args['postID']
    db = get_db()
    cur = db.execute('SELECT postID FROM posts WHERE postID=?', [id_post])
    post = cur.fetchall()
    curr = db.execute('SELECT pTitle, postID, category, text_body, posterID, userID, userName '
                      'FROM posts JOIN users ON posts.posterID = users.userID WHERE postID=?', [id_post])
    posts = curr.fetchall()
    com = db.execute('SELECT COUNT(*) FROM comments WHERE linked_post=?', [id_post])
    num_comments = com.fetchall()[0]
    return render_template('create_comment.html', post=post, user=load_user(), posts=posts, num_comments=num_comments)


@app.route('/addcomment', methods=['POST'])
def add_comment():
    # Adds a new comment to the database
    user = load_user()
    if user is not None:
        user_id = user['userID']
        id_post = request.form['linked_id']
        db = get_db()
        db.execute('INSERT INTO comments (comment_body, linked_post, authorID) VALUES (?, ?, ?)',
                   [request.form['text'], id_post, user_id])
        db.commit()
        flash('Comment successfully created!')
        return redirect(url_for('show_single_post', postID=id_post))
    else:
        flash('Your must be logged in to create a comment!')
        return redirect(url_for('login'))


@app.route('/post')
def make_post():
    # Redirects to a form for writing posts
    return render_template('create_post.html', user=load_user())


@app.route('/add', methods=['POST'])
def add_post():
    # Adds a new post to the database
    user = load_user()
    if user is not None:
        user_id = user['userID']
        db = get_db()
        db.execute('INSERT INTO posts '
                   '(pTitle, category, text_body, posterID, laughScore, sadScore, angryScore, tooPopular) '
                   'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                   [request.form['title'], request.form['category'], request.form['text'], user_id, 0, 0, 0, 0])
        db.commit()
        flash('Your post has been created successfully!')
        return redirect(url_for('show_entries'))
    else:
        flash('Your must be logged in to create a post!')
        return redirect(url_for('login'))


@app.route('/edit', methods=['GET', 'POST'])
def edit_post():
    # Allows the user to edit an existing post
    user = load_user()
    if user is not None:
        db = get_db()
        user_id = user['userID']
        poster_id = request.form['posterID']
        username = user['userName']
        if str(user_id) == str(poster_id) or (username == 'admin'):
            cur = db.execute('SELECT pTitle, postID, category, text_body FROM posts WHERE postID=?',
                             [request.form['postID']])
            post = cur.fetchone()
            return render_template('edit_post.html', post=post, user=load_user())
        else:
            flash('You cannot edit a post that you did not create!')
            return redirect(url_for('login'))
    else:
        flash('You must be logged in to delete a post!')
        return redirect(url_for('login'))


@app.route('/update', methods=['POST'])
def update_post():
    # Makes the desired changes to the database
    user = load_user()
    if user is not None:
        db = get_db()
        db.execute("UPDATE posts SET pTitle=?, category=?, text_body=? WHERE postID=?",
                   [request.form['title'], request.form['category'], request.form['text'], request.form['postID']])
        db.commit()
        return redirect(url_for('show_entries'))
    else:
        flash('Your must be logged in to edit a post!')
        return redirect(url_for('login'))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    # Allows users to create an account
    if request.method == 'POST':
        username = request.form['userName']
        password = request.form['password']
        sec_ans = request.form['secAns']
        db = get_db()
        if username == '':
            flash('Username is required')
        elif password == '':
            flash('Password is required')
        elif sec_ans == '':
            flash('Answer to question is required')
        elif db.execute('SELECT userID FROM users WHERE userName = ?', [username]).fetchone() is not None:
            flash('User {} is already registered'.format(username))
        else:
            db.execute('INSERT INTO users (userName, password, rank, secAns) VALUES (?, ?, ?, ?)',
                       [username, generate_password_hash(password, method='pbkdf2:sha256', salt_length=8), 1,
                        generate_password_hash(sec_ans, method='pbkdf2:sha256', salt_length=8)])
            db.commit()
            user = db.execute('SELECT * FROM users WHERE userName = ?', [username]).fetchone()
            session.clear()
            session['userID'] = user['userID']
            session['admin'] = False
            flash('Welcome to the Site!')
            return redirect(url_for('show_entries'))
    return render_template('signup.html', user=load_user())


@app.route('/login', methods=('GET', 'POST'))
def login():
    # Allows users to log in
    if request.method == 'POST':
        username = request.form['userName']
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE userName = ?', [username]).fetchone()
        if user is None:
            flash('You must first create an account')
            return redirect(url_for('signup'))
        elif username is None:
            flash('Username is incorrect')
        elif not check_password_hash(user['password'], password):
            flash('Passwords do not match')
        else:
            session.clear()
            session['userID'] = user['userID']
            if username == 'admin':
                session['admin'] = True
                session['fPass'] = False
                flash('Welcome Back')
            else:
                session['admin'] = False
                session['fPass'] = False
                flash('You were logged in')
            return redirect(url_for('show_entries'))
    return render_template('login.html', user=load_user())


def load_user():
    # Creates an object containing the users information from the users table based on the userID in the session
    user_id = session.get('userID')
    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            'SELECT * FROM users WHERE userID = ?', [user_id]).fetchone()
    return g.user


@app.route('/logout')
def logout():
    # Allows the user to log out
    session.clear()
    flash('You were logged out')
    return redirect(url_for('show_entries'))


@app.route('/delete', methods=['POST'])
def delete_posts():
    # Allows a user to delete an existing post
    user = load_user()
    if user is not None:
        db = get_db()
        user_id = user['userID']
        id_post = request.form['postID']
        poster_id = request.form['posterID']
        username = user['userName']
        if (str(user_id) == str(poster_id)) or (username == 'admin'):
            db.execute('DELETE FROM posts WHERE postID = ?', [id_post])
            db.commit()
            flash('Your post was removed')
            db.execute('DELETE FROM comments WHERE linked_post = ?', [id_post])
            db.commit()
            return redirect(url_for('show_entries'))
        else:
            flash('You cannot delete a post that you did not create!')
            return redirect(request.referrer)

    else:
        flash('You must be logged in to delete a post!')
        return redirect(url_for('show_entries'))


@app.route('/user_posts', methods=['GET', 'POST'])
def user_posts():
    # Displays all the posts made by the logged in user on a new profile page
    user = load_user()
    if user is not None:
        user_id = user['userID']
        db = get_db()
        filter_it = request.args.get('filter')
        if filter_it == "" or filter_it is None:
            cur = db.execute('SELECT *, COUNT(comments.linked_post) AS post_count, '
                             'SUM(likes.tVote) as vote_total FROM posts '
                             'LEFT JOIN comments ON posts.postID = comments.linked_post '
                             'JOIN users ON users.userID = posts.posterID '
                             'LEFT JOIN likes ON likes.likedPostID = posts.postID '
                             'WHERE posts.tooPopular = 0 AND posterID = ? '
                             'GROUP BY posts.postID ORDER BY postID DESC', [user_id])
        else:
            cur = db.execute('SELECT *, COUNT(comments.linked_post) AS post_count, '
                             'SUM(likes.tVote) as vote_total FROM posts '
                             'LEFT JOIN comments ON posts.postID = comments.linked_post '
                             'JOIN users ON users.userID = posts.posterID '
                             'LEFT JOIN likes ON likes.likedPostID = posts.postID '
                             'WHERE category LIKE ? AND posts.tooPopular = 0 AND posterID = ? '
                             'GROUP BY posts.postID ORDER BY postID DESC', [filter_it, user_id])
            flash("Filtered Unpopular Opinions based on Desired Category")
        post = cur.fetchall()
        cat = db.execute('SELECT DISTINCT category FROM posts WHERE posterID = ? ORDER BY category ASC', [user_id])
        categories = cat.fetchall()
        ranks = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        return render_template('user_profile.html', post=post, categories=categories,
                               id=user_id, user=load_user(), ranks=ranks)
    else:
        flash('Your must be logged in to view your user page!')
        return redirect(url_for('login'))


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    # Displays all post written by the selected user
    user_id = request.args['userID']
    filter_it = request.args.get('filter')
    db = get_db()
    if filter_it == "" or filter_it is None:
        cur = db.execute('SELECT *, COUNT(comments.linked_post) AS post_count, '
                         'SUM(likes.tVote) as vote_total FROM posts '
                         'LEFT JOIN comments ON posts.postID = comments.linked_post '
                         'JOIN users ON users.userID = posts.posterID '
                         'LEFT JOIN likes ON likes.likedPostID = posts.postID '
                         'WHERE posts.tooPopular = 0 AND posterID = ? '
                         'GROUP BY posts.postID ORDER BY postID DESC', [user_id])
    else:
        cur = db.execute('SELECT *, COUNT(comments.linked_post) AS post_count, '
                         'SUM(likes.tVote) as vote_total FROM posts '
                         'LEFT JOIN comments ON posts.postID = comments.linked_post '
                         'JOIN users ON users.userID = posts.posterID '
                         'LEFT JOIN likes ON likes.likedPostID = posts.postID '
                         'WHERE category LIKE ? AND posts.tooPopular = 0 AND posterID = ? '
                         'GROUP BY posts.postID ORDER BY postID DESC', [filter_it, user_id])
        flash("Filtered Unpopular Opinions based on Desired Category")
    post = cur.fetchall()
    curr = db.execute('SELECT DISTINCT category FROM posts WHERE posterID = ? ORDER BY category ASC', [user_id])
    categories = curr.fetchall()
    ranks = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    return render_template('user_profile.html', post=post, categories=categories,
                           id=user_id, user=load_user(), ranks=ranks)


@app.route('/rank')
def rank():
    # Allows an admin to update the rank of a user
    user = load_user()
    if user is not None:
        db = get_db()
        id_user = request.args['userID']
        username = user['userName']
        if username == "admin":
            db.execute("UPDATE users SET rank=? WHERE userID=?",
                       [request.args['rank'], id_user])
            db.commit()
            return redirect(url_for('profile') + "?userID=" + id_user)
    else:
        flash('Your must be logged in to access this!')
        return redirect(url_for('login'))


@app.route('/follow', methods=['POST'])
def follow():
    # Allows a user to follow another user
    user = load_user()
    db = get_db()
    followed_user_name = request.form['username']
    user_id = user['username']
    if followed_user_name == user_id:
        flash('You are not allowed to follow yourself')
        return redirect(url_for('show_entries'))
    cur = db.execute('SELECT * FROM followers WHERE followedUsername = ? AND FollowingUsername = ?',
                     [followed_user_name, user_id])
    duplicate = cur.fetchone()
    if duplicate is not None:
        flash('You are already following this user')
        return redirect(url_for('show_entries'))
    else:
        db.execute('INSERT INTO followers (followedUsername, followingUsername) VALUES (?,?)',
                   [followed_user_name, user_id])
        db.commit()
        return redirect(url_for('show_entries'))


@app.route('/following', methods=['GET', 'POST'])
def following():
    # Allows a user to view posts of the people they have followed
    user = load_user()
    user_id = user['userID']
    filter_it = request.args.get('filter')
    db = get_db()
    if filter_it == "" or filter_it is None:
        cur = db.execute('SELECT *, COUNT(comments.linked_post) AS post_count, '
                         'SUM(likes.tVote) as vote_total FROM posts '
                         'LEFT JOIN comments ON posts.postID = comments.linked_post '
                         'JOIN users ON users.userID = posts.posterID '
                         'LEFT JOIN likes ON likes.likedPostID = posts.postID '
                         'JOIN followers ON followers.followedUsername = users.userName '
                         'WHERE followingUsername = ? AND '
                         'NOT EXISTS (SELECT blockedUsername FROM blockedUsers '
                         'WHERE blockedUsers.blockedUsername = users.userName) '
                         'GROUP BY posts.postID ORDER BY postID DESC', [user['userName']])
    else:
        cur = db.execute('SELECT *, COUNT(comments.linked_post) AS post_count, '
                         'SUM(likes.tVote) as vote_total FROM posts '
                         'LEFT JOIN comments ON posts.postID = comments.linked_post '
                         'JOIN users ON users.userID = posts.posterID '
                         'LEFT JOIN likes ON likes.likedPostID = posts.postID '
                         'JOIN followers ON followers.followedUsername = users.userName '
                         'WHERE followingUsername = ? AND category LIKE ? AND '
                         'NOT EXISTS (SELECT blockedUsername FROM blockedUsers '
                         'WHERE blockedUsers.blockedUsername = users.userName) '
                         'GROUP BY posts.postID ORDER BY postID DESC', [user['userName'], filter_it])
        flash("Filtered Unpopular Opinions based on Desired Category")
    post = cur.fetchall()
    curr = db.execute('SELECT DISTINCT category FROM posts WHERE posterID = ? ORDER BY category ASC', [user_id])
    categories = curr.fetchall()
    ranks = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    return render_template('following_view.html', post=post, categories=categories,
                           id=user_id, user=load_user(), ranks=ranks)


@app.route('/popular', methods=['GET'])
def popular():
    # Shows posts that have gotten too popular for the site
    db = get_db()
    filter_it = request.args.get('filter')
    if filter_it == "" or filter_it is None:
        cur = db.execute('SELECT *, COUNT(comments.linked_post) AS post_count, '
                         'SUM(likes.tVote) as vote_total FROM posts '
                         'LEFT JOIN comments ON posts.postID = comments.linked_post '
                         'JOIN users ON users.userID = posts.posterID '
                         'LEFT JOIN likes ON likes.likedPostID = posts.postID '
                         'WHERE posts.tooPopular = 1 and '
                         'NOT EXISTS (SELECT blockedUsername FROM blockedUsers '
                         'WHERE blockedUsers.blockedUsername = users.userName) '
                         'GROUP BY posts.postID ORDER BY postID DESC')
    else:
        cur = db.execute('SELECT *, COUNT(comments.linked_post) AS post_count, '
                         'SUM(likes.tVote) as vote_total FROM posts '
                         'LEFT JOIN comments ON posts.postID = comments.linked_post '
                         'JOIN users ON users.userID = posts.posterID '
                         'LEFT JOIN likes ON likes.likedPostID = posts.postID '
                         'WHERE category LIKE ? AND posts.tooPopular = 1 and '
                         'NOT EXISTS (SELECT blockedUsername FROM blockedUsers '
                         'WHERE blockedUsers.blockedUsername = users.userName) '
                         'GROUP BY posts.postID ORDER BY postID DESC', [filter_it])
        flash("Filtered Unpopular Opinions based on Desired Category")
    posts = cur.fetchall()
    curr = db.execute('SELECT DISTINCT category FROM posts WHERE posts.tooPopular = 1 ORDER BY category ASC')
    categories = curr.fetchall()
    return render_template('too_popular.html', posts=posts, categories=categories, user=load_user())


@app.route('/block', methods=['POST'])
def block():
    # Allows a user to block another user
    user = load_user()
    db = get_db()
    blocked_user_name = request.form['username']
    username = user['username']
    if blocked_user_name == username:
        flash('You are not allowed to block yourself')
        return redirect(url_for('show_entries'))
    cur = db.execute('SELECT * FROM blockedUsers WHERE blockedUsername = ? AND blockerUsername = ?',
                     [blocked_user_name, username])
    duplicate = cur.fetchone()
    if duplicate is not None:
        flash('You have already blocked this user')
        return redirect(url_for('show_entries'))
    else:
        db.execute('INSERT INTO blockedUsers (blockedUsername, blockerUsername) VALUES (?,?)',
                   [blocked_user_name, username])
        db.commit()
        return redirect(url_for('show_entries'))


@app.route('/unblock', methods=['POST'])
def unblock():
    # Allows a user to unblock another user
    user = load_user()
    db = get_db()
    blocked_user_name = request.form['username']
    username = user['username']
    if blocked_user_name == username:
        flash('You are not allowed to unblock yourself')
        return redirect(url_for('show_entries'))
    else:
        db.execute('DELETE FROM blockedUsers WHERE blockedUsername = ? AND blockerUsername = ?',
                   [blocked_user_name, username])
        db.commit()
        flash('This user has successfully been unblocked')
        return redirect(url_for('show_entries'))


@app.route('/forget', methods=['GET'])
def forget_pass():
    return render_template('forget_pass.html')


@app.route('/change', methods=['GET', 'POST'])
def change_pass():
    db = get_db()
    username = request.form['userName']
    sec_ans = request.form['secAns']
    check = db.execute('SELECT * FROM users WHERE userName = ?',
                       [username]).fetchone()
    if check is not None:
        if check_password_hash(check['secAns'], sec_ans):
            session['fPass'] = True
            return render_template('change_pass.html', username=username)
        else:
            flash("Incorrect security answer")
            return redirect(url_for('forget_pass'))
    else:
        flash("This user is not registered")
        return redirect(url_for('login'))


@app.route('/nPassword', methods=['POST'])
def new_password():
    db = get_db()
    username = request.form['username']
    n_password = request.form['nPassword']
    if session['fPass']:
        db.execute('UPDATE users SET password = ? WHERE userName = ?',
                   [generate_password_hash(n_password, method='pbkdf2:sha256', salt_length=8), username])
        db.commit()
        flash('Successfully changed password')
        session['fPass'] = False
        return redirect(url_for('login'))
    else:
        flash('Not authorized to change password')
        return redirect(url_for('login'))


@app.route('/blocked', methods=['GET', 'POST'])
def blocked():
    # Displays accounts blocked by the user
    user = load_user()
    user_id = user['userID']
    db = get_db()
    cur = db.execute(
        'SELECT * FROM blockedUsers JOIN users on users.userName = blockedUsers.blockerUsername WHERE userID = ?',
        [user_id])
    post = cur.fetchall()
    return render_template('blocked_view.html', post=post,
                           id=user_id, user=load_user())

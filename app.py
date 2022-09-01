# Puffins is a social media site where everyone can share their unpopular opinions
# and find out how unpopular they truly are.
# Written primarily by Ray Loerke

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
    # Connects to the database.
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
# Displays the posts currently in the database
def show_entries():
    db = get_db()
    # Check to see if the user wishes to filter the displayed posts
    filter_it = request.args.get('filter')

    # If they are npt filtering display all posts
    if filter_it == "" or filter_it is None:
        cur = db.execute('SELECT * FROM posts '  # Select all posts
                         'JOIN users ON users.userID = posts.posterID '  # Add user information to each post
                         'WHERE posts.tooPopular = 0 and '  # Exclude too popular posts
                         'NOT EXISTS (SELECT blockedUsername FROM blockedUsers '  # Exclude posts by blocked users
                         'WHERE blockedUsers.blockedUsername = users.userName) '
                         'GROUP BY posts.postID ORDER BY postID DESC')  # Display most recent posts first

    # Otherwise, only display the desired posts
    else:
        cur = db.execute('SELECT * FROM posts '
                         'JOIN users ON users.userID = posts.posterID '
                         'WHERE category LIKE ? AND posts.tooPopular = 0 and '  # Also exclude posts not in the category
                         'NOT EXISTS (SELECT blockedUsername FROM blockedUsers '
                         'WHERE blockedUsers.blockedUsername = users.userName) '
                         'GROUP BY posts.postID ORDER BY postID DESC', [filter_it])

        # Notify the user that posts have been filtered
        flash("Filtered Unpopular Opinions based on Desired Category")
    posts = cur.fetchall()

    # Find list of unique categories to be displayed in the filter dropdown
    curr = db.execute('SELECT DISTINCT category FROM posts WHERE posts.tooPopular = 0 ORDER BY category ASC')
    categories = curr.fetchall()

    # Count the number of comments and likes
    num_comments, num_likes = count_values(db)

    # Pass necessary information to the html template and render
    return render_template('show_posts.html', posts=posts, categories=categories,
                           user=load_user(), num_comments=num_comments, num_likes=num_likes)


@app.route('/upVote', methods=['POST'])
# Allow  users to upvote a post
def upvote():
    user = load_user()
    db = get_db()

    # Get the id of the post the user wants to upvote
    posted_id = request.form["postID"]

    # Find that post in the database
    cur = db.execute('SELECT * FROM likes WHERE likedPostID = ? AND likingUserID = ?',
                     [posted_id, user['userID']])
    repeat = cur.fetchone()

    # Check if the user has already voted on this post (admins can vote more than once)
    if (repeat is None) or (user['userName'] == 'admin'):

        # Make sure the user is signed in
        if user is not None:

            # Add entry into likes table
            db.execute('INSERT INTO likes (likingUserID, likedPostID, tVote) VALUES (?, ?, ?)',
                       [user['userID'], posted_id, 1])
            db.commit()

            # Calculate the new vote total
            vote_total = db.execute('SELECT *, SUM(likes.tVote) AS vote_count FROM likes WHERE likedPostID = ?',
                                    [posted_id]).fetchone()

            # If the post receives too many upvotes move it to the too popular posts section
            if vote_total['vote_count'] > 20:
                db.execute('UPDATE posts SET tooPopular = 1 WHERE postID = ?', [posted_id])
                db.commit()

                # Notify the user their vote made the post too popular
                flash('Your vote has made this post too popular! It has been moved to the Too Popular Posts section.')
                return redirect(url_for('popular'))
            else:
                return redirect(url_for('show_entries'))
        else:
            # Tell the user they must log in to vote
            flash('Your must be logged in to vote!')
            return redirect(request.referrer)

    # If the user is changing their vote find the database entry for their old vote and modify it
    elif repeat['tVote'] == -1:
        db.execute("UPDATE likes SET tVote = ? WHERE likingUserID = ? and likedPostID = ?",
                   [1, user['userID'], posted_id])
        db.commit()
        return redirect(url_for('show_entries'))

    # Tell the user they can't vote twice
    else:
        flash('You have already voted')
        return redirect(url_for('show_entries'))


@app.route('/downVote', methods=['POST'])
# Allow  users to downvote a post
# See upvote for documentation
def downvote():
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


@app.route('/view', methods=['GET', 'POST'])
# Displays a single post and its comments
def show_single_post():

    # Find the id of the desired post
    id_post = request.args['postID']
    db = get_db()

    # Get the desired post from the database
    cur = db.execute('SELECT pTitle, postID, category, text_body, posterID, userID, userName, rank FROM posts '
                     'JOIN users ON posts.posterID = users.userID WHERE postID=?', [id_post])  # Get the posters info
    post = cur.fetchall()

    # Get all comments made on the desired post
    curr = db.execute('SELECT userName, comment_body, userID, authorID, linked_post FROM comments '
                      'JOIN users ON comments.authorID = users.userID WHERE linked_post=?', [id_post])
    comments = curr.fetchall()

    # Count the number of comments made about the desired post
    com = db.execute('SELECT COUNT(*) FROM comments WHERE linked_post=?', [id_post])
    num_comments = com.fetchall()[0]

    # Calculate the vote total for the desired post
    likes = db.execute('SELECT SUM(likes.tVote) AS vote_total FROM likes WHERE likedPostID = ?',
                       [id_post]).fetchall()[0]

    # Pass necessary information to the html template and render
    return render_template('single_post_view.html', post=post, comments=comments,
                           num_comments=num_comments, user=load_user(), likes=likes)


@app.route('/comment', methods=['GET'])
# Redirects to a form for writing comments
def make_comment():

    # Find the id of the post the user wants to comment on
    id_post = request.args['postID']
    db = get_db()
    cur = db.execute('SELECT postID FROM posts WHERE postID=?', [id_post])  # Is this line necessary?
    post = cur.fetchall()

    # Select that post from the database
    curr = db.execute('SELECT pTitle, postID, category, text_body, posterID, userID, userName '
                      'FROM posts JOIN users ON posts.posterID = users.userID WHERE postID=?', [id_post])
    posts = curr.fetchall()

    # Count the number of comments on the desired post
    com = db.execute('SELECT COUNT(*) FROM comments WHERE linked_post=?', [id_post])
    num_comments = com.fetchall()[0][0]

    # Calculate the vote total for the desired post
    up = db.execute('SELECT SUM(likes.tVote) FROM likes WHERE likedPostID=?', [id_post])
    num_votes = up.fetchall()[0][0]

    # Pass necessary information to the html template and render
    return render_template('create_comment.html', post=post, user=load_user(),
                           posts=posts, num_comments=num_comments, num_votes=num_votes)


@app.route('/addcomment', methods=['POST'])
# Adds a new comment to the database
def add_comment():
    user = load_user()

    # Make sure the user is logged in
    if user is not None:

        # Get the user and posts id's
        user_id = user['userID']
        id_post = request.form['linked_id']
        db = get_db()

        # Add the comment into the database
        db.execute('INSERT INTO comments (comment_body, linked_post, authorID) VALUES (?, ?, ?)',
                   [request.form['text'], id_post, user_id])
        db.commit()

        # Notify the user their comment was made successfully
        flash('Comment successfully created!')
        return redirect(url_for('show_single_post', postID=id_post))

    # Notify the user they must log in to comment
    else:
        flash('Your must be logged in to create a comment!')
        return redirect(url_for('login'))


@app.route('/post')
# Redirects to a form for writing posts
def make_post():
    return render_template('create_post.html', user=load_user())


@app.route('/add', methods=['POST'])
# Adds a new post to the database
def add_post():
    user = load_user()

    # Make sure the user is logged in
    if user is not None:

        # Get the users id
        user_id = user['userID']
        db = get_db()

        # Add the post into the database
        db.execute('INSERT INTO posts '
                   '(pTitle, category, text_body, posterID, tooPopular) '
                   'VALUES (?, ?, ?, ?, ?)',
                   [request.form['title'], request.form['category'], request.form['text'], user_id, 0])
        db.commit()

        # Notify the user their post was made successfully
        flash('Your post has been created successfully!')
        return redirect(url_for('show_entries'))

    # Tell the user they must be logged in to post
    else:
        flash('Your must be logged in to create a post!')
        return redirect(url_for('login'))


@app.route('/edit', methods=['GET', 'POST'])
# Allows the user to edit an existing post
def edit_post():
    user = load_user()

    # Make sure the user is logged in
    if user is not None:
        db = get_db()

        # Get the user's id and the id of the post they want to edit
        user_id = user['userID']
        poster_id = request.form['posterID']
        username = user['userName']

        # Make sure the user is trying to edit one of their posts
        if str(user_id) == str(poster_id) or (username == 'admin'):

            # Display the post the user wants to edit
            cur = db.execute('SELECT pTitle, postID, category, text_body FROM posts WHERE postID=?',
                             [request.form['postID']])
            post = cur.fetchone()

            # Redirect the user to a form for editing their post
            return render_template('edit_post.html', post=post, user=load_user())
        else:
            flash('You cannot edit a post that you did not create!')
            return redirect(url_for('login'))
    else:
        flash('You must be logged in to delete a post!')
        return redirect(url_for('login'))


@app.route('/update', methods=['POST'])
# Update the database with the users desired post modifications
def update_post():
    user = load_user()

    # Make sure the user is logged in
    if user is not None:
        db = get_db()

        # Update the post in the databse with the desired changes
        db.execute("UPDATE posts SET pTitle=?, category=?, text_body=? WHERE postID=?",
                   [request.form['title'], request.form['category'], request.form['text'], request.form['postID']])
        db.commit()
        return redirect(url_for('show_entries'))
    else:
        flash('Your must be logged in to edit a post!')
        return redirect(url_for('login'))


@app.route('/signup', methods=['GET', 'POST'])
# Allows users to create an account
def signup():
    if request.method == 'POST':

        # Get the users information
        username = request.form['userName']
        password = request.form['password']
        sec_ans = request.form['secAns']
        db = get_db()

        # MAke sure no entries are bland
        if username == '':
            flash('Username is required')
        elif password == '':
            flash('Password is required')
        elif sec_ans == '':
            flash('Answer to question is required')

        # Make sure a user with this username does not already exist
        elif db.execute('SELECT userID FROM users WHERE userName = ?', [username]).fetchone() is not None:
            flash('User {} is already registered'.format(username))

        # Add the user into the database with their password and security question answer salted and hashed
        else:
            db.execute('INSERT INTO users (userName, password, rank, secAns) VALUES (?, ?, ?, ?)',
                       [username, generate_password_hash(password, method='pbkdf2:sha256', salt_length=8), 1,
                        generate_password_hash(sec_ans, method='pbkdf2:sha256', salt_length=8)])
            db.commit()
            user = db.execute('SELECT * FROM users WHERE userName = ?', [username]).fetchone()

            # Log the user into their new account
            session.clear()
            session['userID'] = user['userID']
            session['admin'] = False
            flash('Welcome to the Site!')
            return redirect(url_for('show_entries'))
    return render_template('signup.html', user=load_user())


@app.route('/login', methods=('GET', 'POST'))
# Allows users to log in
def login():
    if request.method == 'POST':

        # Get the username and password entered
        username = request.form['userName']
        password = request.form['password']
        db = get_db()

        # Find database entry for the user
        user = db.execute('SELECT * FROM users WHERE userName = ?', [username]).fetchone()

        # Notify the user if their account does not exist
        if user is None:
            flash('You must first create an account')
            return redirect(url_for('signup'))

        # Make sure the username field is not empty
        elif username is None:
            flash('Username is incorrect')

        # Check to see if the password matches
        elif not check_password_hash(user['password'], password):
            flash('Passwords do not match')
        else:

            # Log the user into their account
            session.clear()
            session['userID'] = user['userID']

            # Check if the user is an admin
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


# Creates an object containing the users' information from the users table based on the userID in the session
def load_user():
    user_id = session.get('userID')
    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            'SELECT * FROM users WHERE userID = ?', [user_id]).fetchone()
    return g.user


@app.route('/logout')
# Allows the user to log out
def logout():
    session.clear()
    flash('You were logged out')
    return redirect(url_for('show_entries'))


@app.route('/delete', methods=['POST'])
# Allows a user to delete an existing post
def delete_posts():
    user = load_user()

    # Make sure the user is logged in
    if user is not None:
        db = get_db()

        # Get the user's id and the id of the post they want to delete
        user_id = user['userID']
        id_post = request.form['postID']
        poster_id = request.form['posterID']
        username = user['userName']

        # Make sure the user is trying to delete a post they wrote
        if (str(user_id) == str(poster_id)) or (username == 'admin'):

            # Delete the post from the database
            db.execute('DELETE FROM posts WHERE postID = ?', [id_post])
            db.commit()
            flash('Your post was removed')

            # Delete all associated comments
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
# Displays all the posts made by the logged-in user
def user_posts():
    user = load_user()

    # Make sure the user is logged in
    if user is not None:
        user_id = user['userID']

        # Call a helper function to display all posts made by a single user
        return user_post_view(user_id)

    else:
        flash('Your must be logged in to view your user page!')
        return redirect(url_for('login'))


@app.route('/profile', methods=['GET', 'POST'])
# Displays all post written by the selected user
def profile():
    user_id = request.args['userID']

    # Call a helper function to display all posts made by a single user
    return user_post_view(user_id)


@app.route('/rank')
# Allows an admin to update the rank of a user
def rank():
    user = load_user()

    # Make sure the user is logged in
    if user is not None:
        db = get_db()

        # Get the user's id
        id_user = request.args['userID']
        username = user['userName']

        # Make sure the user is an admin
        if username == "admin":

            # Update the desired users rank in the database
            db.execute("UPDATE users SET rank=? WHERE userID=?",
                       [request.args['rank'], id_user])
            db.commit()

            # Return to the desired users profile page
            return redirect(url_for('profile') + "?userID=" + id_user)
    else:
        flash('Your must be logged in to access this!')
        return redirect(url_for('login'))


@app.route('/follow', methods=['POST'])
# Allows a user to follow another user
def follow():
    user = load_user()
    db = get_db()

    # Get the id's of the user and who they want to follow
    followed_user_name = request.form['username']
    user_id = user['username']

    # Check if user is trying to follow themselves
    if followed_user_name == user_id:
        flash('You are not allowed to follow yourself')
        return redirect(url_for('show_entries'))

    # See if this entry already exists in the followers table
    cur = db.execute('SELECT * FROM followers WHERE followedUsername = ? AND FollowingUsername = ?',
                     [followed_user_name, user_id])
    duplicate = cur.fetchone()
    if duplicate is not None:
        flash('You are already following this user')
        return redirect(url_for('show_entries'))
    else:

        # Add a new entry into the followers table
        db.execute('INSERT INTO followers (followedUsername, followingUsername) VALUES (?,?)',
                   [followed_user_name, user_id])
        db.commit()
        return redirect(url_for('show_entries'))


@app.route('/following', methods=['GET', 'POST'])
# Allows a user to view posts of the people they have followed
def following():
    user = load_user()

    # Get the user's id and any filters
    user_id = user['userID']
    filter_it = request.args.get('filter')
    db = get_db()

    # If there is no filter display all posts
    if filter_it == "" or filter_it is None:
        cur = db.execute('SELECT * FROM posts '  # Select all posts
                         'JOIN users ON users.userID = posts.posterID '  # Add user information
                         'JOIN followers ON followers.followedUsername = users.userName '  # Filter out posts by others
                         'WHERE followingUsername = ? AND '
                         'NOT EXISTS (SELECT blockedUsername FROM blockedUsers '  # Filter out blocked user's posts
                         'WHERE blockedUsers.blockedUsername = users.userName) '
                         'GROUP BY posts.postID ORDER BY postID DESC', [user['userName']])  # Order by newest post first
    else:
        cur = db.execute('SELECT * FROM posts '
                         'JOIN users ON users.userID = posts.posterID '
                         'JOIN followers ON followers.followedUsername = users.userName '
                         'WHERE followingUsername = ? AND category LIKE ? AND '  # Also, filter by category
                         'NOT EXISTS (SELECT blockedUsername FROM blockedUsers '
                         'WHERE blockedUsers.blockedUsername = users.userName) '
                         'GROUP BY posts.postID ORDER BY postID DESC', [user['userName'], filter_it])
        flash("Filtered Unpopular Opinions based on Desired Category")
    post = cur.fetchall()

    # Select unique categories for the filter dropdown
    curr = db.execute('SELECT DISTINCT category FROM posts WHERE posterID = ? ORDER BY category ASC', [user_id])
    categories = curr.fetchall()

    # List all possible ranks
    ranks = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    num_comments, num_likes = count_values(db)

    # Pass necessary information to the html template and render
    return render_template('following_view.html', post=post, categories=categories,
                           id=user_id, user=load_user(), ranks=ranks, num_comments=num_comments, num_likes=num_likes)


@app.route('/popular', methods=['GET'])
# Show posts that have gotten too popular for the site
def popular():
    db = get_db()

    # Get any filters
    filter_it = request.args.get('filter')

    # Check if there are filters
    if filter_it == "" or filter_it is None:
        cur = db.execute('SELECT * FROM posts '  # Get all posts
                         'JOIN users ON users.userID = posts.posterID '  # Add user's information
                         'WHERE posts.tooPopular = 1 and '  # Filter out posts that are not too popular
                         'NOT EXISTS (SELECT blockedUsername FROM blockedUsers '  # Filter out blocked suer's posts
                         'WHERE blockedUsers.blockedUsername = users.userName) '
                         'GROUP BY posts.postID ORDER BY postID DESC')  # Order by newest post first
    else:
        cur = db.execute('SELECT * FROM posts '
                         'JOIN users ON users.userID = posts.posterID '
                         'WHERE category LIKE ? AND posts.tooPopular = 1 and '  # Also, filter by category
                         'NOT EXISTS (SELECT blockedUsername FROM blockedUsers '
                         'WHERE blockedUsers.blockedUsername = users.userName) '
                         'GROUP BY posts.postID ORDER BY postID DESC', [filter_it])
        flash("Filtered Unpopular Opinions based on Desired Category")
    posts = cur.fetchall()

    # Select unique categories for the filter dropdown
    curr = db.execute('SELECT DISTINCT category FROM posts WHERE posts.tooPopular = 1 ORDER BY category ASC')
    categories = curr.fetchall()

    num_comments, num_likes = count_values(db)

    # Pass necessary information to the html template and render
    return render_template('too_popular.html', posts=posts, categories=categories,
                           user=load_user(), num_comments=num_comments, num_likes=num_likes)


@app.route('/block', methods=['POST'])
# Allows a user to block another user
def block():
    user = load_user()
    db = get_db()

    # Get the id of the user and the id of the person they want to block
    blocked_user_name = request.form['username']
    username = user['username']

    # Users can't block themselves
    if blocked_user_name == username:
        flash('You are not allowed to block yourself')
        return redirect(url_for('show_entries'))

    # Check existing entries in the database
    cur = db.execute('SELECT * FROM blockedUsers WHERE blockedUsername = ? AND blockerUsername = ?',
                     [blocked_user_name, username])
    duplicate = cur.fetchone()

    # Check for duplicate blocks
    if duplicate is not None:
        flash('You have already blocked this user')
        return redirect(url_for('show_entries'))
    else:

        # Add the block into the blocked users table
        db.execute('INSERT INTO blockedUsers (blockedUsername, blockerUsername) VALUES (?,?)',
                   [blocked_user_name, username])
        db.commit()
        return redirect(url_for('show_entries'))


@app.route('/unblock', methods=['POST'])
# Allows a user to unblock another user
def unblock():
    user = load_user()
    db = get_db()

    # Get the id of the user and the id of the person they want to unblock
    blocked_user_name = request.form['username']
    username = user['username']

    # Users can't unblock themselves
    if blocked_user_name == username:
        flash('You are not allowed to unblock yourself')
        return redirect(url_for('show_entries'))
    else:

        # Delete the block in the blocked users table
        db.execute('DELETE FROM blockedUsers WHERE blockedUsername = ? AND blockerUsername = ?',
                   [blocked_user_name, username])
        db.commit()
        flash('This user has successfully been unblocked')
        return redirect(url_for('show_entries'))


@app.route('/forget', methods=['GET'])
# Renders the page for resetting your password
def forget_pass():
    return render_template('forget_pass.html')


@app.route('/change', methods=['GET', 'POST'])
# Allows the user to change their password
def change_pass():
    db = get_db()

    # Get the users username and security question answer
    username = request.form['userName']
    sec_ans = request.form['secAns']

    # Select the user database entry
    check = db.execute('SELECT * FROM users WHERE userName = ?',
                       [username]).fetchone()

    # Check if this user exists
    if check is not None:

        # Make sure the security answer matches
        if check_password_hash(check['secAns'], sec_ans):
            session['fPass'] = True

            # Render the page for entering a new password
            return render_template('change_pass.html', username=username)
        else:
            flash("Incorrect security answer")
            return redirect(url_for('forget_pass'))
    else:
        flash("This user is not registered")
        return redirect(url_for('login'))


@app.route('/nPassword', methods=['POST'])
# Allows the user to enter their new password
def new_password():
    db = get_db()

    # Get the user's username and new password
    username = request.form['username']
    n_password = request.form['nPassword']

    # Check if the user provided the right security question answer
    if session['fPass']:

        # Update their database entry with their new password
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
# Display accounts blocked by the user
def blocked():
    user = load_user()

    # Get the user's id
    user_id = user['userID']
    db = get_db()

    # Get list of blocked users from the database
    cur = db.execute(
        'SELECT * FROM blockedUsers JOIN users on users.userName = blockedUsers.blockerUsername WHERE userID = ?',
        [user_id])
    post = cur.fetchall()

    # Pass necessary information to the html template and render
    return render_template('blocked_view.html', post=post,
                           id=user_id, user=load_user())


# This helper function is used to calculate the number of comments and vote total for posts
def count_values(db):
    post_ids = []

    # Get all posts from the database
    ids = db.execute('SELECT DISTINCT postID FROM posts')

    # Create a list of unique posts
    for i in ids:
        post_ids += i

    # Count the number of comments each post has
    num_comments = {}
    for i in post_ids:
        num_comments[i] = db.execute('SELECT COUNT(commentID) FROM comments WHERE linked_post=?', [i]).fetchall()[0][0]

    # Calculate the vote total for each post
    num_likes = {}
    for i in post_ids:
        num_likes[i] = db.execute('SELECT SUM(tVote) FROM likes WHERE likedPostID=?', [i]).fetchall()[0][0]

    # Fix number for posts with no votes
    for i in post_ids:
        if num_likes[i] is None:
            num_likes[i] = 0
    return num_comments, num_likes


# This helper function displays posts from a single user
def user_post_view(user_id):

    # Get any filters
    filter_it = request.args.get('filter')
    db = get_db()

    # Check if there are filters
    if filter_it == "" or filter_it is None:
        cur = db.execute('SELECT * FROM posts '  # Select all posts
                         'JOIN users ON users.userID = posts.posterID '  # Add user information
                         'WHERE posterID = ? '  # Filter out posts not made by the desired user
                         'GROUP BY posts.postID ORDER BY postID DESC', [user_id])  # Show the newest posts first
    else:
        cur = db.execute('SELECT * FROM posts '
                         'JOIN users ON users.userID = posts.posterID '
                         'WHERE category LIKE ? AND posterID = ? '  # Also, filter by category
                         'GROUP BY posts.postID ORDER BY postID DESC', [filter_it, user_id])
        flash("Filtered Unpopular Opinions based on Desired Category")
    post = cur.fetchall()

    # Select unique categories for the filter dropdown
    curr = db.execute('SELECT DISTINCT category FROM posts WHERE posterID = ? ORDER BY category ASC', [user_id])
    categories = curr.fetchall()

    # List all possible ranks
    ranks = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    num_comments, num_likes = count_values(db)

    # Pass necessary information to the html template and render
    return render_template('user_profile.html', post=post, categories=categories,
                           id=user_id, user=load_user(), ranks=ranks, num_comments=num_comments, num_likes=num_likes)

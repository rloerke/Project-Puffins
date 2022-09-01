# Unit tests for the Puffins application
# Written by Ray Loerke

import os
import app as puffins
import unittest
import tempfile


class PuffinsTestCase(unittest.TestCase):

    # Set up the testing environment
    def setUp(self):
        self.db_fd, puffins.app.config['DATABASE'] = tempfile.mkstemp()
        puffins.app.testing = True
        self.app = puffins.app.test_client()
        with puffins.app.app_context():
            puffins.init_db()

    # Close the testing environment
    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(puffins.app.config['DATABASE'])

    # A helper function for creating a new account
    def signup(self, username, password, sec_ans):
        return self.app.post('/signup', data=dict(
            userName=username,
            password=password,
            secAns=sec_ans
        ), follow_redirects=True)

    # A helper function for logging into an account
    def login(self, username, password):
        return self.app.post('/login', data=dict(
            userName=username,
            password=password
        ), follow_redirects=True)

    # A helper function for logging out of an account
    def logout(self):
        return self.app.get('/logout', follow_redirects=True)

    # This test checks if navigation bar is displayed correctly
    def test_layout(self):
        rv = self.app.get('/')

        # Make sure navbar is displaying the right elements when not logged in
        assert b'Puffins' in rv.data
        assert b'Filter' in rv.data
        assert b'Log In' in rv.data
        assert b'Sign Up' in rv.data

        # Make sure the navbar is showing the right elements when logged in
        self.signup('Bob', 'default', 'teacher')
        rv2 = self.app.get('/')
        assert b'Puffins' in rv2.data
        assert b'Filter' in rv2.data
        assert b'Post' in rv2.data
        assert b'Log Out' in rv2.data
        assert b'Bob' in rv2.data

    # This test checks if a post can be added to the database and displayed to the user
    def test_messages(self):
        # Create an account and make a post
        self.signup('Bob', 'default', 'teacher')
        rv = self.app.post('/add', data=dict(
            title='Title',
            category='Test Category',
            text='This is some sample text.'
        ), follow_redirects=True)

        # Check if the post is being displayed
        assert b'Title' in rv.data
        assert b'Test Category' in rv.data
        assert b'This is some sample text.' in rv.data

    # This test checks if the post writing form is displayed correctly
    def test_posting_layout(self):
        rv = self.app.get('/post')

        # Checks if the right text boxes are being displayed
        assert b'Title' in rv.data
        assert b'Category' in rv.data
        assert b'Text' in rv.data

    # This test checks that the delete path correctly deletes a single entry
    def test_delete(self):
        # Create an account and make two posts
        self.signup('Bob', 'default', 'teacher')
        self.app.post('/add', data=dict(
            title='My New Cat',
            category='Pets',
            text='I just got a new cat and she is cool.'
        ), follow_redirects=True)
        self.app.post('/add', data=dict(
            title='My New Car',
            category='Cars',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)

        # Delete the first post
        rv = self.app.post('/delete', data=dict(postID='1', posterID='2'),
                           follow_redirects=True)

        # Check that the first post is not displayed but the second is
        assert b'My New Cat' not in rv.data
        assert b'Pets' not in rv.data
        assert b'I just got a new cat and she is cool.' not in rv.data
        assert b'My New Car' in rv.data
        assert b'Cars' in rv.data
        assert b'I just got a new car and it is blue.' in rv.data

    # This test checks if the edit path successfully changes a post and displays the changes
    def test_edit(self):
        # Create an account and make a post
        self.signup('Bob', 'default', 'teacher')
        self.app.post('/add', data=dict(
            title='My New Car',
            category='Cars',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)

        # Edit that post
        self.app.post('/edit', data=dict(postID='1', posterID='2'),
                      follow_redirects=True)
        rv = self.app.post('/update', data=dict(
            title='My New Awesome Car',
            category='Cars',
            text='I just got a new car and it is blue and red.',
            postID='1'
        ), follow_redirects=True)

        # Check if the changes are being displayed
        assert b'My New Awesome Car' in rv.data
        assert b'Cars' in rv.data
        assert b'I just got a new car and it is blue and red.' in rv.data
        assert b'My New Car' not in rv.data
        assert b'I just got a new car and it is blue.' not in rv.data

    # This test checks if comments can be added and viewed
    def test_comment(self):
        # Make an account and make a post
        self.signup('Bob', 'default', 'teacher')
        self.app.post('/add', data=dict(
            title='My New Car',
            category='Cars',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)

        # Add comments to that post
        self.app.post('/comment?postID=1', follow_redirects=True)
        self.app.post('/addcomment', data=dict(
            linked_id='1',
            text='That is very cool, what type of car?'
        ), follow_redirects=True)
        self.app.post('/comment?postID=1', follow_redirects=True)
        rv = self.app.post('/addcomment', data=dict(
            linked_id='1',
            text='It is a Ford Pickup'
        ), follow_redirects=True)

        # Check if the comments are being displayed
        assert b'My New Car' in rv.data
        assert b'Cars' in rv.data
        assert b'I just got a new car and it is blue.' in rv.data
        assert b'That is very cool, what type of car?' in rv.data
        assert b'It is a Ford Pickup' in rv.data

    # This test checks if number of comments is displayed correctly
    def test_comment_number(self):
        # Create an account and make a post
        self.signup('Bob', 'default', 'teacher')
        rv = self.app.post('/add', data=dict(
            title='My New Car',
            category='Cars',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)

        # Check if the number of comments displayed is zero
        assert b'Comment (0)' in rv.data

        # Add comments and check that the display is updating
        self.app.post('/comment?postID=1', follow_redirects=True)
        rv2 = self.app.post('/addcomment', data=dict(
            linked_id='1',
            text='That is very cool, what type of car?'
        ), follow_redirects=True)
        assert b'Comment (1)' in rv2.data
        self.app.post('/comment?postID=1', follow_redirects=True)
        rv3 = self.app.post('/addcomment', data=dict(
            linked_id='1',
            text='That is very cool, what type of car?'
        ), follow_redirects=True)
        assert b'Comment (2)' in rv3.data

    # This test checks if comments are displayed on the single post view page
    def test_comment_display(self):
        # Create an account, add a post and add comments
        self.signup('Joe', 'default', 'teacher')
        self.app.post('/add', data=dict(
            title='My New Car',
            category='Vehicles',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)
        self.app.post('/comment?postID=1', follow_redirects=True)
        self.app.post('/addcomment', data=dict(
            linked_id='1',
            text='That is very cool, what type of car?'
        ), follow_redirects=True)
        self.app.post('/comment?postID=1', follow_redirects=True)
        self.app.post('/addcomment', data=dict(
            linked_id='1',
            text='It is a Ford Pickup'
        ), follow_redirects=True)
        rv = self.app.get('/')

        # Check that the post and comments are being displayed
        assert b'My New Car' in rv.data
        assert b'Vehicles' in rv.data
        assert b'I just got a new car and it is blue.' in rv.data
        assert b'That is very cool, what type of car?' not in rv.data
        assert b'It is a Ford Pickup' not in rv.data

    # This test checks if comments are being displayed on the correct posts
    def test_comment_multiplication(self):
        # Create an account, add some post and add one comments to each
        self.signup('Bob', 'default', 'teacher')
        self.app.post('/add', data=dict(
            title='My New Car',
            category='Vehicles',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)
        self.app.post('/comment?postID=1', follow_redirects=True)
        self.app.post('/addcomment', data=dict(
            linked_id='1',
            text='That is very cool, what type of car?'
        ), follow_redirects=True)
        self.app.post('/add', data=dict(
            title='My New Cat',
            category='Pets',
            text='I just got a new cat and she is cool.'
        ), follow_redirects=True)
        self.app.post('/comment?postID=2', follow_redirects=True)
        rv = self.app.post('/addcomment', data=dict(
            linked_id='2',
            text='Cool, I like cool cats.'
        ), follow_redirects=True)

        # Check if the first post and its comment are being displayed and not the second comment
        assert b'My New Cat' in rv.data
        assert b'Pets' in rv.data
        assert b'I just got a new cat and she is cool.' in rv.data
        assert b'Cool, I like cool cats.' in rv.data
        assert b'My New Car' not in rv.data
        assert b'Vehicles' not in rv.data
        assert b'I just got a new car and it is blue.' not in rv.data
        assert b'That is very cool, what type of car?' not in rv.data
        self.app.get('/')
        rv2 = self.app.post('/view?postID=1', follow_redirects=True)

        # Check if the second post and its comment are being displayed and not the first
        assert b'My New Cat' not in rv2.data
        assert b'Pets' not in rv2.data
        assert b'I just got a new cat and she is cool.' not in rv2.data
        assert b'Cool, I like cool cats.' not in rv2.data
        assert b'My New Car' in rv2.data
        assert b'Vehicles' in rv2.data
        assert b'I just got a new car and it is blue.' in rv2.data
        assert b'That is very cool, what type of car?' in rv2.data

    # This test checks if posts are being filtered correctly
    def test_filter(self):
        # Create an account and make some posts
        self.signup('Bob', 'default', 'teacher')
        self.app.post('/add', data=dict(
            title='Title1',
            category='Movies',
            text='I do not like Batman'
        ), follow_redirects=True)
        self.app.post('/add', data=dict(
            title="Title2",
            category='Pizza',
            text='Pizza is horrible'
        ), follow_redirects=True)
        rv = self.app.get('/?filter=Movies')

        # Check if only the filtered post is being displayed
        assert b'Title1' in rv.data
        assert b'I do not like Batman' in rv.data
        assert b'Title2' not in rv.data
        assert b'Pizza is horrible' not in rv.data
        rv2 = self.app.get('/?filter=Pizza')
        assert b'Title1' not in rv2.data
        assert b'I do not like Batman' not in rv2.data
        assert b'Title2' in rv2.data
        assert b'Pizza is horrible' in rv2.data

    # This test checks if ranks are displaying
    def test_rank_display(self):
        # Create an account and make a post
        self.signup('Bob', 'default', 'teacher')
        rv = self.app.post('/add', data=dict(
            title='My New Car',
            category='Vehicles',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)

        # Check if the users rank is being displayed
        assert b'Rank: 1' in rv.data
        self.logout()
        self.login('admin', 'wj5O78u9*ARx')

        # Change the users rank
        rv2 = self.app.post('/add', data=dict(
            title='My New Car',
            category='Vehicles',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)

        # Check if the new rank is being displayed
        assert b'Rank: 10' in rv2.data

    # This test checks if admin can change the rank of users
    def test_rank_change(self):
        # Create an account and make a post
        self.signup('Jim', 'default', 'teacher')
        rv = self.app.post('/add', data=dict(
            title='My New Car',
            category='Vehicles',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)

        # Check that the correct rank is being displayed
        assert b'Rank: 1' in rv.data
        self.logout()
        self.login('admin', 'wj5O78u9*ARx')
        rv2 = self.app.get('/profile?userID=2')
        assert b'Ranks' in rv2.data
        rv3 = self.app.get("/rank?rank=4&userID=2", follow_redirects=True)
        assert b'Rank: 4' in rv3.data

    # This test checks if the follower system works and displays the followed user's posts on a different page.
    def test_following_user(self):
        # Create an account and add a post
        self.signup('Bob', 'default', 'teacher')
        self.app.post('/add', data=dict(
            title='My New Car',
            category='Vehicles',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)
        self.logout()

        # Create a second account and follow the first account
        self.signup('John', 'default', 'teacher')
        self.app.post('/profile?userID=2', follow_redirects=True)
        self.app.post('/follow', data=dict(
            username='Bob'
        ), follow_redirects=True)
        rv = self.app.get('/following', follow_redirects=True)

        # Check if the followed user's posts are being displayed
        assert b'My New Car' in rv.data
        assert b'Vehicles' in rv.data
        assert b'I just got a new car and it is blue.'

    # This test checks if the upvote system is working correctly
    def test_upvote(self):
        # Create an account and make a post
        self.signup('Bob', 'default', 'teacher')
        self.app.post('/add', data=dict(
            title='My New Car',
            category='Vehicles',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)

        # Upvote that post
        rv = self.app.post('/upVote', data=dict(
            postID=1
        ), follow_redirects=True)

        # Check if the vote count is correct
        assert b'Upvote (1)' in rv.data

    # This test checks if the blocking system works
    def test_blocking_user(self):
        # Create an account and make a post
        self.signup('Bob', 'default', 'teacher')
        self.app.post('/add', data=dict(
            title='My New Sweet Car',
            category='Vehicles',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)
        self.logout()

        # Create a second account and block the first
        self.signup('John', 'default', 'teacher')
        self.app.post('/profile?userID=2', follow_redirects=True)
        self.app.post('/block', data=dict(
            username='Bob'
        ), follow_redirects=True)
        rv = self.app.get('/show_entries', follow_redirects=True)

        # Check that the blocked user's post is not being displayed
        assert b'My New Sweet Car' not in rv.data
        assert b'Vehicles' not in rv.data
        assert b'I just got a new car and it is blue.' not in rv.data

    # This test checks if the downvote system is working correctly
    def test_downvote(self):
        # Create an account, make a post and downvote it
        self.signup('Bob', 'default', 'teacher')
        self.app.post('/add', data=dict(
            title='My New Car',
            category='Vehicles',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)
        rv = self.app.post('/downVote', data=dict(
            postID=1
        ), follow_redirects=True)

        # Check that the vote total is correct
        assert b'Upvote (-1)' in rv.data

    # This test checks if changes password system works
    def test_remember_password(self):
        # Create an account and try to change the password
        self.signup('Bob', 'default', 'default')
        self.logout()
        self.app.get('/login')
        self.app.get('/forgot')
        self.app.post('/change', data=dict(
            userName='Bob',
            secAns='default'
        ), follow_redirects=True)
        rv = self.app.post('/nPassword', data=dict(
            nPassword='NewPassword',
            username='Bob'
        ), follow_redirects=True)

        # Check that the user was notified that the change was successful
        assert b'Successfully changed password' in rv.data

    # This test checks if the unblocking system works
    def test_unblocking_user(self):
        # Create an account
        self.signup('Bob', 'default', 'teacher')
        self.logout()

        # Create a second account and block the first
        self.signup('John', 'default', 'teacher')
        self.app.post('/profile?userID=2', follow_redirects=True)
        self.app.post('/block', data=dict(
            username='Bob'
        ), follow_redirects=True)
        self.app.get('/show_entries', follow_redirects=True)

        # Then, unblock the first user
        self.app.post('/unblock', data=dict(
            username='Bob'
        ), follow_redirects=True)
        rv = self.app.get('/blocked', follow_redirects=True)

        # Check if the user is listed as blocked
        assert b'Bob' not in rv.data

    # This test checks if too popular posts are being moved to new section
    def test_too_popular(self):
        # Create an account and make a post
        self.signup('Bob', 'default', 'default')
        self.login('Bob', 'default')
        self.app.post('/add', data=dict(
            title='My New Car',
            category='Vehicles',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)
        self.logout()

        # Log in as admin and upvote the post 20 times
        self.login('admin', 'wj5O78u9*ARx')
        for x in range(19):
            self.app.post('/upVote', data=dict(postID='1'), follow_redirects=True)
        rv = self.app.post('/upVote', data=dict(postID='1'), follow_redirects=True)

        # Check if the post is still on the main page
        assert b'My New Car' in rv.data
        assert b'Vehicles' in rv.data
        assert b'I just got a new car and it is blue.' in rv.data
        rv2 = self.app.post('/upVote', data=dict(postID='1'), follow_redirects=True)

        # Check if the vote has been moved to the too popular posts page
        assert b'Too Popular Posts' in rv2.data
        assert b'My New Car' in rv2.data
        assert b'Vehicles' in rv2.data
        assert b'I just got a new car and it is blue.' in rv2.data
        rv3 = self.app.get('/')

        # Check that the post no longer appears on the main page
        assert b'My New Car' not in rv3.data
        assert b'Vehicles' not in rv3.data
        assert b'I just got a new car and it is blue.' not in rv3.data


if __name__ == '__main__':
    unittest.main()

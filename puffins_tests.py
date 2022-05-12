import os
import app as puffins
import unittest
import tempfile


class PuffinsTestCase(unittest.TestCase):

    def setUp(self):
        self.db_fd, puffins.app.config['DATABASE'] = tempfile.mkstemp()
        puffins.app.testing = True
        self.app = puffins.app.test_client()
        with puffins.app.app_context():
            puffins.init_db()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(puffins.app.config['DATABASE'])

    def signup(self, username, password, sec_ans):
        return self.app.post('/signup', data=dict(
            userName=username,
            password=password,
            secAns=sec_ans
        ), follow_redirects=True)

    def login(self, username, password):
        return self.app.post('/login', data=dict(
            userName=username,
            password=password
        ), follow_redirects=True)

    def logout(self):
        return self.app.get('/logout', follow_redirects=True)

    def test_layout(self):
        # Checks if navigation bar is displayed
        rv = self.app.get('/')
        assert b'Puffins' in rv.data
        assert b'Filter' in rv.data
        assert b'Log In' in rv.data
        assert b'Sign Up' in rv.data
        self.signup('Bob', 'default', 'teacher')
        rv2 = self.app.get('/')
        assert b'Puffins' in rv2.data
        assert b'Filter' in rv2.data
        assert b'Post' in rv2.data
        assert b'Log Out' in rv2.data
        assert b'Bob' in rv2.data

    def test_messages(self):
        # Checks to see if a post can be added to the database and displayed to the user
        self.signup('Bob', 'default', 'teacher')
        rv = self.app.post('/add', data=dict(
            title='Title',
            category='Test Category',
            text='This is some sample text.'
        ), follow_redirects=True)
        assert b'Title' in rv.data
        assert b'Test Category' in rv.data
        assert b'This is some sample text.' in rv.data

    def test_posting_layout(self):
        # Checks to see if the post writing form is displayed correctly
        rv = self.app.get('/post')
        assert b'Title' in rv.data
        assert b'Category' in rv.data
        assert b'Text' in rv.data

    def test_delete(self):
        # Checks that the delete path correctly deletes a single entry
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
        rv = self.app.post('/delete', data=dict(postID='1', posterID='2'),
                           follow_redirects=True)
        assert b'My New Cat' not in rv.data
        assert b'Pets' not in rv.data
        assert b'I just got a new cat and she is cool.' not in rv.data
        assert b'My New Car' in rv.data
        assert b'Cars' in rv.data
        assert b'I just got a new car and it is blue.' in rv.data

    def test_edit(self):
        # Checks if the edit path successfully changes a post and displays the changes
        self.signup('Bob', 'default', 'teacher')
        self.app.post('/add', data=dict(
            title='My New Car',
            category='Cars',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)
        self.app.post('/edit', data=dict(postID='1', posterID='2'),
                      follow_redirects=True)
        rv = self.app.post('/update', data=dict(
            title='My New Awesome Car',
            category='Cars',
            text='I just got a new car and it is blue and red.',
            postID='1'
        ), follow_redirects=True)
        assert b'My New Awesome Car' in rv.data
        assert b'Cars' in rv.data
        assert b'I just got a new car and it is blue and red.' in rv.data
        assert b'My New Car' not in rv.data
        assert b'I just got a new car and it is blue.' not in rv.data

    def test_comment(self):
        # Checks if comments can be added and viewed
        self.signup('Bob', 'default', 'teacher')
        self.app.post('/add', data=dict(
            title='My New Car',
            category='Cars',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)
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
        assert b'My New Car' in rv.data
        assert b'Cars' in rv.data
        assert b'I just got a new car and it is blue.' in rv.data
        assert b'That is very cool, what type of car?' in rv.data
        assert b'It is a Ford Pickup' in rv.data

    def test_comment_number(self):
        # Checks if number of comments is displayed correctly
        self.signup('Bob', 'default', 'teacher')
        rv = self.app.post('/add', data=dict(
            title='My New Car',
            category='Cars',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)
        assert b'Comment (0)' in rv.data
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

    def test_comment_display(self):
        # Checks if comments are only displayed on the single post view page

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
        assert b'My New Car' in rv.data
        assert b'Vehicles' in rv.data
        assert b'I just got a new car and it is blue.' in rv.data
        assert b'That is very cool, what type of car?' not in rv.data
        assert b'It is a Ford Pickup' not in rv.data

    def test_comment_multiplication(self):
        # Checks if comments are only being displayed on the correct posts
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
        assert b'My New Cat' not in rv2.data
        assert b'Pets' not in rv2.data
        assert b'I just got a new cat and she is cool.' not in rv2.data
        assert b'Cool, I like cool cats.' not in rv2.data
        assert b'My New Car' in rv2.data
        assert b'Vehicles' in rv2.data
        assert b'I just got a new car and it is blue.' in rv2.data
        assert b'That is very cool, what type of car?' in rv2.data

    def test_filter(self):
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
        assert b'Title1' in rv.data
        assert b'I do not like Batman' in rv.data
        assert b'Title2' not in rv.data
        assert b'Pizza is horrible' not in rv.data
        rv2 = self.app.get('/?filter=Pizza')
        assert b'Title1' not in rv2.data
        assert b'I do not like Batman' not in rv2.data
        assert b'Title2' in rv2.data
        assert b'Pizza is horrible' in rv2.data

    def test_rank_display(self):
        # Checks if ranks are displaying
        self.signup('Bob', 'default', 'teacher')
        rv = self.app.post('/add', data=dict(
            title='My New Car',
            category='Vehicles',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)
        assert b'Rank: 1' in rv.data
        self.logout()
        self.login('admin', 'wj5O78u9*ARx')
        rv2 = self.app.post('/add', data=dict(
            title='My New Car',
            category='Vehicles',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)
        assert b'Rank: 10' in rv2.data

    def test_rank_change(self):
        # Checks if admin can change the rank of users
        self.signup('Jim', 'default', 'teacher')
        rv = self.app.post('/add', data=dict(
            title='My New Car',
            category='Vehicles',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)
        assert b'Rank: 1' in rv.data
        self.logout()
        self.login('admin', 'wj5O78u9*ARx')
        rv2 = self.app.get('/profile?userID=2')
        assert b'Ranks' in rv2.data
        rv3 = self.app.get("/rank?rank=4&userID=2", follow_redirects=True)
        assert b'Rank: 4' in rv3.data

    def test_following_user(self):
        # check if the follower system works and displays the posts on a different page.
        self.signup('Bob', 'default', 'teacher')
        self.app.post('/add', data=dict(
            title='My New Car',
            category='Vehicles',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)
        self.logout()
        self.signup('John', 'default', 'teacher')
        self.app.post('/profile?userID=2', follow_redirects=True)
        self.app.post('/follow', data=dict(
            username='Bob'
        ), follow_redirects=True)
        rv = self.app.get('/following', follow_redirects=True)
        assert b'My New Car' in rv.data
        assert b'Vehicles' in rv.data
        assert b'I just got a new car and it is blue.'

    def test_upvote(self):
        # checks upvote system
        self.signup('Bob', 'default', 'teacher')
        self.app.post('/add', data=dict(
            title='My New Car',
            category='Vehicles',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)
        rv = self.app.post('/upVote', data=dict(
            postID=1
        ), follow_redirects=True)
        assert b'Upvote (1)' in rv.data

    def test_blocking_user(self):
        # check if the blocking system works
        self.signup('John', 'default', 'teacher')
        self.app.post('/profile?userID=2', follow_redirects=True)
        self.app.post('/block', data=dict(
            username='Bob'
        ), follow_redirects=True)
        rv = self.app.get('/show_entries', follow_redirects=True)
        assert b'My New Car' not in rv.data
        assert b'Vehicles' not in rv.data
        assert b'I just got a new car and it is blue.' not in rv.data

    def test_downvote(self):
        # checks downvote system
        self.signup('Bob', 'default', 'teacher')
        self.app.post('/add', data=dict(
            title='My New Car',
            category='Vehicles',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)
        rv = self.app.post('/downVote', data=dict(
            postID=1
        ), follow_redirects=True)
        assert b'Upvote (-1)' in rv.data

    def test_remember_password(self):
        # checks if changes password system works
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
        assert b'Successfully changed password' in rv.data

    def test_unblocking_user(self):
        # check if the unblocking system works
        self.signup('John', 'default', 'teacher')
        self.app.post('/profile?userID=2', follow_redirects=True)
        self.app.post('/block', data=dict(
            username='Bob'
        ), follow_redirects=True)
        self.app.get('/show_entries', follow_redirects=True)
        self.app.post('/unblock', data=dict(
            username='Bob'
        ), follow_redirects=True)
        rv = self.app.get('/blocked', follow_redirects=True)
        assert b'Bob' not in rv.data

    def reactions(self):
        self.signup('Bob', 'default', 'teacher')
        self.app.post('/add', data=dict(
            title='Man Utd',
            category='Football',
            text='They beat PSG'
        ), follow_redirects=True)
        rv = self.app.post('/react_laugh', data=dict(
            postID=1
        ), follow_redirects=True)
        assert b'react_laugh (1)' in rv.data
        assert b'react_sad (1)' not in rv.data
        assert b'react_angry (1)' not in rv.data
        self.app.post('/add', data=dict(
            title='Man Utd',
            category='Football',
            text='They beat PSG'
        ), follow_redirects=True)
        rv2 = self.app.post('/react_laugh', data=dict(
            postID=1
        ), follow_redirects=True)
        assert b'react_laugh (1)' not in rv2.data
        assert b'react_sad (1)' in rv2.data
        assert b'react_angry (1)' not in rv2.data
        self.app.post('/add', data=dict(
            title='Man Utd',
            category='Football',
            text='They beat PSG'
        ), follow_redirects=True)
        rv3 = self.app.post('/react_laugh', data=dict(
            postID=1
        ), follow_redirects=True)
        assert b'react_laugh (1)' not in rv3.data
        assert b'react_sad (1)' not in rv3.data
        assert b'react_angry (1)' in rv3.data

    def test_too_popular(self):
        # Checks if too popular posts are being moved to new section
        self.signup('Bob', 'default', 'default')
        self.login('Bob', 'default')
        self.app.post('/add', data=dict(
            title='My New Car',
            category='Vehicles',
            text='I just got a new car and it is blue.'
        ), follow_redirects=True)
        self.logout()
        self.login('admin', 'wj5O78u9*ARx')
        for x in range(19):
            self.app.post('/upVote', data=dict(postID='1'), follow_redirects=True)
        rv = self.app.post('/upVote', data=dict(postID='1'), follow_redirects=True)
        assert b'My New Car' in rv.data
        assert b'Vehicles' in rv.data
        assert b'I just got a new car and it is blue.' in rv.data
        rv2 = self.app.post('/upVote', data=dict(postID='1'), follow_redirects=True)
        assert b'Too Popular Posts' in rv2.data
        assert b'My New Car' in rv2.data
        assert b'Vehicles' in rv2.data
        assert b'I just got a new car and it is blue.' in rv2.data
        rv3 = self.app.get('/')
        assert b'My New Car' not in rv3.data
        assert b'Vehicles' not in rv3.data
        assert b'I just got a new car and it is blue.' not in rv3.data


if __name__ == '__main__':
    unittest.main()

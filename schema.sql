drop table if exists users;
create table users (
    userID integer primary key autoincrement unique,
    userName text not null unique,
    password text not null,
    rank integer not null,
    secAns text not null
);

drop table if exists posts;
create table posts (
    pTitle text not null,
    postID integer primary key autoincrement unique,
    posterID integer not null, --References users.userID
    text_body text not null,
    'category' text not null,
    tooPopular integer not null
);

drop table if exists comments;
create table comments (
    commentID integer primary key autoincrement unique,
    authorID integer not null, --References users.userID
    comment_body text not null,
    linked_post integer not null --References posts.postID
);

drop table if exists likes;
create table likes (
   likingUserID integer not null, --References user.userID
   likedPostID integer not null, --References post.postID
   tVote integer not null --Type of vote, 1 for upvote, -1 for downvote
);

drop table if exists followers;
create table followers (
    followedUsername text not null,
    followingUsername text not null
);

drop table if exists blockedUsers;
create table blockedUsers(
    blockedUsername text not null,
    blockerUsername text not null
);

INSERT INTO users (userName, password, rank, secAns) VALUES ("admin", "pbkdf2:sha256:150000$hixxO9pd$89972db09313f7b66249688cd3c9a8b71457662b8a2303092ebe487d648d5363", 10, 'a');
-- Password: wj5O78u9*ARx
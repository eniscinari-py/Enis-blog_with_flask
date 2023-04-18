from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import datetime
from sqlalchemy import select, ForeignKey
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
import os
from functools import wraps
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap(app)

# CONNECT TO DB
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'blog.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
is_logged = False
admin = False


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)


# CONFIGURE TABLES

Base = declarative_base()


gravatar = Gravatar(
    app,
    rating='g',
    default='retro',
    force_default=False,
    force_lower=False,
    use_ssl=False,
    base_url=None
)


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    author_id = db.Column(db.Integer, ForeignKey("users.id"))
    author = relationship("User", back_populates="children")
    comments = relationship("Comment", back_populates="parent_post")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    children = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="author_comment")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    comment = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, ForeignKey("users.id"))
    author_comment = relationship("User", back_populates="comments")
    post_id = db.Column(db.Integer, ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")


# with app.app_context():
#     db.create_all()
#     db.session.commit()


def admin_only(fn):
    wraps(fn)

    def inner(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return fn(*args, **kwargs)

    return inner


@app.route('/', methods=['GET', 'POST'])
def get_all_posts():
    posts = db.session.execute(select(BlogPost)).scalars().all()
    authors = db.session.execute(select(User.name)).scalars().all()
    return render_template("index.html", all_posts=posts, is_logged=is_logged, authors=authors)


@app.route('/register', methods=['GET', 'POST'])
def register():
    email_404 = request.args.get('email_404')
    the_form = RegisterForm()
    emails = db.session.execute(select(User.email)).scalars().all()
    with app.app_context():
        if the_form.email.data not in emails:
            new_user = User(
                name=the_form.name.data,
                email=the_form.email.data,
                password=the_form.password.data,
            )
            if request.method == 'POST':
                print(generate_password_hash(password=the_form.password.data, method='pbkdf2:sha256', salt_length=16))
                db.session.add(new_user)
                db.session.commit()
                return redirect(url_for('get_all_posts'))
        else:
            message = "Your email is already part of our database. Please login! "
            return redirect(url_for('login', message=message, is_logged=is_logged))
    return render_template("register.html", form=the_form, email_404=email_404, is_logged=is_logged)


@app.route('/login', methods=['POST', 'GET'])
def login():
    global is_logged
    pass_match = None
    form = LoginForm()
    error = request.args.get('error')
    message = request.args.get('message')
    if form.validate_on_submit():
        email_entered = form.email.data
        password_entered = form.password.data
        password_db = db.session.execute(select(User.password).filter_by(email=email_entered)).scalar_one_or_none()
        name_db = db.session.execute(select(User.name).filter_by(email=email_entered)).scalar_one_or_none()
        user = db.session.execute(select(User).filter_by(email=email_entered)).scalar_one_or_none()
        if user:
            if password_db == password_entered:
                if login_user(user):
                    is_logged = True
                    return redirect(url_for('get_all_posts', is_logged=is_logged, admin=admin))
            else:
                pass_match = f"Wrong credentials {name_db.split(' ')[0]}. Please check your password! "
        else:
            email_404 = "This email does not exist in our database. Please Sign up!"
            return redirect(url_for('register', email_404=email_404))
    return render_template("login.html", form=form, message=message, pass_match=pass_match, error=error)


@app.route('/logout')
@login_required
def logout():
    global is_logged
    is_logged = False
    logout_user()
    return redirect(url_for('get_all_posts', is_logged=is_logged))


@app.route("/post/<int:index>", methods=['GET', 'POST'])
# @login_required
def show_post(index):
    form = CommentForm()
    author = None
    comments = None
    posts = db.session.execute(db.select(BlogPost.id)).all()
    author_id = db.session.execute(select(BlogPost.author_id).filter_by(id=index)).scalar_one()
    requested_post = None
    for blog_post in posts:
        print(blog_post)
        print(current_user.is_authenticated)
        if blog_post[0] == index:
            author = db.session.execute(select(User.name).filter_by(id=author_id)).scalar_one()
            requested_post = db.session.execute(select(BlogPost).filter_by(id=index)).scalar_one()
            if request.method == 'POST':
                if current_user.is_authenticated:
                    with app.app_context():
                        new_comment = Comment(
                            comment=form.comment.data,
                            author_id=current_user.id,
                            post_id=index
                        )
                        db.session.add(new_comment)
                        db.session.commit()
                else:
                    error = "You need to login to comment! "
                    return redirect(url_for("login", error=error), code=403)
        comments = db.session.execute(select(Comment).filter_by(post_id=index)).scalars().all()
    return render_template("post.html", post=requested_post, is_logged=is_logged, author=author, form=form, comments=comments)


@app.route("/about")
def about():
    return render_template("about.html", is_logged=is_logged)


@app.route("/contact")
def contact():
    return render_template("contact.html", is_logged=is_logged)


@app.route('/new-post', methods=['POST', 'GET'], endpoint='new_post')
@login_required
@admin_only
def new_post():
    form = CreatePostForm()
    title = "New Post"
    if request.method == 'POST':
        now = datetime.now()
        with app.app_context():
            post = BlogPost(
                title=form.title.data,
                subtitle=form.subtitle.data,
                date=now.strftime("%B %d, %Y"),
                body=form.body.data,
                author_id=current_user.id,
                img_url=form.img_url.data,
            )
            db.session.add(post)
            db.session.commit()
            print("Post added successfully!")
            author = db.session.execute(select(User.name).filter_by(id=post.author_id)).scalar_one()
            return redirect(url_for('get_all_posts', is_logged=is_logged, author=author))
    return render_template('make-post.html', form=form, title=title, is_logged=is_logged)


@app.route('/edit-post/<post_id>', methods=['GET', 'POST'], endpoint='edit_post')
@login_required
@admin_only
def edit_post(post_id):
    the_post = db.session.execute(select(BlogPost).filter_by(id=post_id)).scalar_one()
    form = CreatePostForm(
        title=the_post.title,
        subtitle=the_post.subtitle,
        author=the_post.author,
        img_url=the_post.img_url,
        body=the_post.body,
    )
    if request.method == 'GET':
        title = "Edit Post"
        return render_template('make-post.html', title=title, form=form, is_logged=is_logged)
    the_post.title = form.title.data
    the_post.subtitle = form.subtitle.data
    the_post.body = form.body.data
    the_post.author = form.author.data
    the_post.img_url = form.img_url.data
    db.session.commit()
    return redirect(url_for('show_post', index=post_id, is_logged=is_logged))


@app.route("/delete-post/<post_id>", endpoint='delete_post')
@login_required
@admin_only
def delete_post(post_id):
    to_be_del = db.session.execute(select(BlogPost).filter_by(id=post_id)).scalar_one()
    db.session.delete(to_be_del)
    db.session.commit()
    return redirect(url_for("get_all_posts", is_logged=is_logged))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)

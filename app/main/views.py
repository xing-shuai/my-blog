import json
import os
import uuid
from PIL import Image

from flask import render_template, session, redirect, url_for, abort, flash, request, make_response
from flask_login import login_required, current_user

from app import db
from app.models import Permission, User, Role, Post, Comment
from . import main
from .forms import EditProfileForm, EditProfileAdminForm, PostForm, CommentForm
from ..decorators import permission_required, admin_required


@main.route('/', methods=["POST", "GET"])
def index():
    form = PostForm()
    if current_user.can(Permission.WRITE_ARTICLES) and form.validate_on_submit():
        post = Post(title=form.title.data, body=form.body.data, author=current_user._get_current_object())
        db.session.add(post)
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    show_type = '0'
    if current_user.is_authenticated:
        show_type = str(request.cookies.get('show_type', '0'))
    if show_type == '1':
        query = current_user.followed_posts
    elif show_type == '0':
        query = Post.query
    else:
        query = current_user.posts
    pagination = query.order_by(Post.timestamp.desc()).paginate(page, per_page=10, error_out=False)
    posts = pagination.items
    return render_template("index.html", show_type=show_type, form=form, posts=posts, pagination=pagination,
                           current_page='Home')


@main.route('/all')
@login_required
def show_all():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_type', '0', max_age=30 * 24 * 60 * 60)
    return resp


@main.route('/followed')
@login_required
def show_followed():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_type', '1', max_age=30 * 24 * 60 * 60)
    return resp


@main.route('/my_posts')
@login_required
def my_posts():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_type', '2', max_age=30 * 24 * 60 * 60)
    return resp


@main.route("/user/<username>")
def user(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        abort(404)
    page = request.args.get('page', 1, type=int)
    pagination = user.posts.order_by(Post.timestamp.desc()).paginate(page, per_page=10, error_out=False)
    posts = pagination.items
    return render_template('user.html', user=user, posts=posts, pagination=pagination, current_page='Profile')


@main.route("/edit_profile", methods=["POST", "GET"])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.location = form.location.data
        current_user.about_me = form.about_me.data
        db.session.add(current_user)
        flash('Your profile has been updated.')
        return redirect(url_for('.user', username=current_user.username))
    form.name.data = current_user.name
    form.location.data = current_user.location
    form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', form=form, current_page='Profile', user=current_user)


@main.route("/edit_profile_admin/<int:id>", methods=["POST", "GET"])
@login_required
@admin_required
def edit_profile_admin(id):
    user = User.query.get_or_404(id)
    form = EditProfileAdminForm(user=user)
    if form.validate_on_submit():
        user.username = form.username.data
        user.role = Role.query.get(form.role.data)
        user.name = form.name.data
        user.location = form.location.data
        user.about_me = form.about_me.data
        db.session.add(user)
        flash('The profile has been updated.')
        return redirect(url_for('.user', username=user.username))
    form.username.data = user.username
    form.role.data = user.role_id
    form.name.data = user.name
    form.location.data = user.location
    form.about_me.data = user.about_me
    return render_template('edit_profile.html', form=form, current_page='Profile', user=user)


@main.route("/post/<int:id>", methods=["POST", "GET"])
def post(id):
    post = Post.query.get_or_404(id)
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(body=form.body.data, post=post, author=current_user._get_current_object())
        db.session.add(comment)
        flash('Your comment has been published.')
        return redirect(url_for('.post', id=post.id, page=-1))
    page = request.args.get('page', 1, type=int)
    if page == -1:
        page = (post.comments.count() - 1) / 10 + 1
    pagination = post.comments.order_by(Comment.timestamp.asc()).paginate(page, 10, error_out=False)
    comments = pagination.items
    return render_template('post.html', posts=[post], form=form, comments=comments, pagination=pagination)


@main.route('/edit_post/<int:id>', methods=["POST", "GET"])
@login_required
def edit_post(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        post.body = form.body.data
        db.session.add(post)
        flash('The post has been updated')
        return redirect(url_for('.post', id=post.id))
    form.body.data = post.body
    form.title.data = post.title
    return render_template('edit_post.html', form=form)


@main.route('/delete_post/<int:id>')
@login_required
def delete_post(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and not current_user.can(Permission.ADMINISTER):
        abort(403)
    db.session.delete(post)
    flash('You have deleted that post.')
    return redirect(url_for(".index"))


@main.route('/follow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    if current_user.is_following(user):
        flash('You are already following this user.')
        return redirect(url_for('.user', username=username))
    current_user.follow(user)
    db.session.commit()
    flash('You are now following %s.' % username)
    return redirect(url_for('.user', username=username))


@main.route('/unfollow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    if not current_user.is_following(user):
        flash('You are not following this user.')
        return redirect(url_for('.user', username=username))
    current_user.unfollow(user)
    db.session.commit()
    flash('You are not following %s.' % username)
    return redirect(url_for('.user', username=username))


@main.route('/followers/<username>')
def followers(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    page = request.args.get("page", 1, type=int)
    pagination = user.followers.paginate(page, 10, error_out=False)
    follows = [{"user": item.follower, 'timestamp': item.timestamp} for item in pagination.items]
    return render_template('followers.html', user=user, title='Followers of', endpoint='.followers',
                           pagination=pagination, follows=follows)


@main.route('/followed_by/<username>')
def followed_by(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    page = request.args.get("page", 1, type=int)
    pagination = user.followed.paginate(page, 10, error_out=False)
    follows = [{"user": item.followed, 'timestamp': item.timestamp} for item in pagination.items]
    return render_template('followers.html', user=user, title='Followed by', endpoint='.followed_by',
                           pagination=pagination, follows=follows)


@main.route('/moderate')
@login_required
@permission_required(Permission.MODERATE_COMMENT)
def moderate():
    page = request.args.get("page", 1, type=int)
    pagination = Comment.query.order_by(Comment.timestamp.desc()).paginate(page, 20, error_out=False)
    comments = pagination.items
    return render_template('moderate.html', comments=comments, pagination=pagination, page=page,
                           current_page='Moderate')


@main.route("/moderate/enable/<int:id>")
@login_required
@permission_required(Permission.MODERATE_COMMENT)
def moderate_enable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = False
    db.session.add(comment)
    flash('This comment has been enabled.')
    return redirect(url_for('.moderate', page=request.args.get("page", 1, type=int)))


@main.route('/moderate/disable/<int:id>')
@login_required
@permission_required(Permission.MODERATE_COMMENT)
def moderate_disable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = True
    db.session.add(comment)
    flash('This comment has been disabled.')
    return redirect(url_for('.moderate', page=request.args.get("page", 1, type=int)))


@main.route('/upload/user_head', methods=['POST', 'GET'])
@login_required
def upload_user_head():
    try:
        path = os.path.abspath(os.path.join(os.getcwd(), './app/static/user/head/'))
        if not os.path.exists(path):
            os.makedirs(path)
        file = request.files["head"]
        file_name = str(uuid.uuid1()) + "." + file.filename.split(".")[-1:][0]
        username = request.form['user']
        crop_x_offset = int(float(request.form['crop_x_offset']))
        crop_y_offset = int(float(request.form['crop_y_offset']))
        crop_length = int(float(request.form['crop_length']))
        crop_x_offset = crop_x_offset if crop_x_offset >= 0 else 0
        full_name = path + "/" + file_name
        user = User.query.filter_by(username=username).first()
        if user.head_img:
            os.remove(path + "/" + user.head_img)
        file.save(full_name)
        img = Image.open(full_name)
        height = img.size[1]
        width = img.size[0]
        if crop_length > width or crop_length > height:
            crop_length = width if width > height else height
        if crop_x_offset < 0:
            crop_x_offset = 0
        if crop_x_offset > width:
            crop_x_offset = width - crop_length
        if crop_y_offset < 0:
            crop_y_offset = 0
        if crop_y_offset > height:
            crop_y_offset = height - crop_length

        box = (crop_x_offset, crop_y_offset, crop_x_offset + crop_length, crop_y_offset + crop_length)
        roi = img.crop(box)
        os.remove(full_name)
        roi.save(full_name)
        user.head_img = file_name
        db.session.add(user)
        return json.dumps({"code": 1})
    except:
        return json.dumps({"code": -1})


@main.route("/admin")
@login_required
@admin_required
def for_admin_only():
    return "For administrators!"


@main.route("/moderator")
@login_required
@permission_required(Permission.MODERATE_COMMENT)
def for_moderator_only():
    return "For comment moderators!"

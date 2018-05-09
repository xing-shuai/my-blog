from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField
from wtforms.validators import Length, DataRequired, Regexp, ValidationError
from flask_pagedown.fields import PageDownField
from app.models import Role, User


class EditProfileForm(FlaskForm):
    name = StringField("Real name", validators=[Length(1, 64)])
    location = StringField("Location", validators=[Length(1, 64)])
    about_me = TextAreaField('About me')
    submit = SubmitField("Submit")


class EditProfileAdminForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Regexp('^[A-Za-z][A-Za-z0-9_.]*$', 0,
                                                                          'Username must have only letters,numbers,dots or underscores'),
                                                   Length(1, 64)])
    role = SelectField('Role', coerce=int)
    name = StringField("Real name", validators=[Length(1, 64)])
    location = StringField("Location", validators=[Length(1, 64)])
    about_me = TextAreaField('About me')
    submit = SubmitField("Submit")

    def __init__(self, user, *args, **kwargs):
        super(EditProfileAdminForm, self).__init__(*args, **kwargs)
        self.role.choices = [(role.id, role.name) for role in Role.query.order_by(Role.name).all()]
        self.user = user

    def validate_username(self, filed):
        if filed.data != self.user.username and User.query.filter_by(username=filed.data).first():
            raise ValidationError('Username already in use.')


class PostForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    body = PageDownField("What's on your mind?", validators=[DataRequired()])
    submit = SubmitField('Submit')


class CommentForm(FlaskForm):
    body = PageDownField('Enter your comment', validators=[DataRequired()])
    submit = SubmitField('Submit')

# Add to your existing forms or create forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

class SendMessageForm(FlaskForm):
    recipient_id = SelectField('Recipient', coerce=int, validators=[DataRequired()])
    subject = StringField('Subject', validators=[Optional(), Length(max=255)])
    content = TextAreaField('Message', validators=[DataRequired(), Length(min=1, max=5000)])
    submit = SubmitField('Send Message')

class ReplyMessageForm(FlaskForm):
    content = TextAreaField('Reply', validators=[DataRequired(), Length(min=1, max=5000)])
    submit = SubmitField('Send Reply')
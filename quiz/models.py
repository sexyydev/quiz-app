from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.urls import reverse
import uuid
from django.utils import timezone
from django.core.exceptions import ValidationError

class MyUserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, username, password, **extra_fields)


class CustomUser(AbstractBaseUser):
    username = models.CharField(max_length=30, unique=True)
    email = models.EmailField(max_length=255, unique=True)
    first_name = models.CharField(max_length=100, default='')
    last_name = models.CharField(max_length=100, default='')
    registration_number = models.CharField(max_length=255, unique=True, default="some_default_value")
    ROLE_CHOICES = (('quiz_master', 'Quiz Master'), ('quiz_taker', 'Quiz Taker'))
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='quiz_taker')
    additional_info = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = MyUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

    @property
    def is_quiz_master(self):
        return self.role == 'quiz_master'

    @property
    def is_quiz_taker(self):
        return self.role == 'quiz_taker'


class Quiz(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField()
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='quizzes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    time_limit = models.PositiveIntegerField(default=0)
    total_score = models.FloatField(default=0.0)

    def update_total_score(self):
        self.total_score = self.questions.aggregate(total=models.Sum('mark'))['total'] or 0.0
        self.save()

    def clean(self):
        if self.time_limit < 0:
            raise ValidationError('Time limit cannot be negative.')

    def __str__(self):
        return self.title

    def get_quiz_link(self):
        return reverse('access-quiz', kwargs={'quiz_uuid': self.uuid})


class Question(models.Model):
    TYPE_CHOICES = (
        ('MCQ', 'Multiple Choice Question'),
        ('TF', 'True/False'),
        ('SA', 'Short Answer')
    )

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    type = models.CharField(max_length=3, choices=TYPE_CHOICES)
    content = models.TextField()
    mcq_option1 = models.CharField(max_length=255, blank=True, null=True)
    mcq_option2 = models.CharField(max_length=255, blank=True, null=True)
    mcq_option3 = models.CharField(max_length=255, blank=True, null=True)
    mcq_option4 = models.CharField(max_length=255, blank=True, null=True)
    correct_answer = models.TextField(null=True, blank=True)
    category = models.CharField(max_length=50, blank=True, null=True)
    keywords = models.TextField(null=True, blank=True)
    criteria = models.TextField(null=True, blank=True)
    mark = models.FloatField(default=1.0)
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='questions')
    position = models.PositiveIntegerField(default=0)  # Add this field to track order

    def clean(self):
        if self.type == 'MCQ':
            if not all([self.mcq_option1, self.mcq_option2, self.mcq_option3, self.mcq_option4]):
                raise ValidationError('All MCQ options must be provided.')
            if not self.correct_answer:
                raise ValidationError('Correct answer must be provided for MCQ.')

    def __str__(self):
        return self.content


class Answer(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, related_name='answers', on_delete=models.CASCADE)
    answer = models.TextField()
    is_correct = models.BooleanField(default=False)
    graded_by_ai = models.BooleanField(default=False)
    feedback = models.TextField(null=True, blank=True)
    time_spent = models.DurationField(blank=True, null=True)

    def __str__(self):
        return f'{self.user} - {self.question}'


class Result(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    score = models.FloatField()
    completion_status = models.CharField(max_length=20)
    feedback = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    @property
    def score_percentage(self):
        raw_percentage = (self.score / self.quiz.total_score) * 100
        return float(f"{raw_percentage:.3g}")

    def __str__(self):
        return f'{self.user} - {self.quiz}'

from django.contrib import admin
from .models import CustomUser, Quiz, Question, Answer, Result

# Registering the models with the admin site
admin.site.register(CustomUser)
admin.site.register(Quiz)
admin.site.register(Question)
admin.site.register(Answer)
admin.site.register(Result)

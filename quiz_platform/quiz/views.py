import uuid
import json
from django.db import IntegrityError, transaction
from django.contrib import messages
from django.contrib.auth import authenticate, login as django_login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, Max, Min, Sum, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from .utils import detailed_feedback
from .models import CustomUser, Quiz, Question, Answer, Result
from .forms import UserLoginForm, UserRegistrationForm, ChangePasswordForm, UserProfileForm

import logging

logger = logging.getLogger(__name__)

# Registration, login, and profile management views
def register_view(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                username = form.cleaned_data.get('username')
                messages.success(request, f'Account created for {username}!')
                return redirect('login')
            except IntegrityError:
                form.add_error('registration_number', 'A user with this registration number already exists.')
    else:
        form = UserRegistrationForm()
    return render(request, 'register.html', {'form': form})

@login_required
def quiz_master_dashboard(request):
    user = request.user
    quizzes = Quiz.objects.filter(created_by=user)
    total_quizzes = quizzes.count()
    total_participants = Result.objects.filter(quiz__created_by=user).values('user').distinct().count()
    average_score = Result.objects.filter(quiz__created_by=user).aggregate(Avg('score'))['score__avg'] or 0
    recent_activities = Result.objects.filter(quiz__created_by=user).order_by('-created_at')[:10]

    context = {
        'total_quizzes': total_quizzes,
        'total_participants': total_participants,
        'average_score': average_score,
        'recent_activities': recent_activities,
        'quizzes': quizzes
    }

    return render(request, 'quiz_master_dashboard.html', context)

@login_required
def profile_view(request):
    user = request.user
    dashboard_url = 'quiz_master_dashboard' if user.is_quiz_master else 'quiz_taker_dashboard'

    context = {
        'user': user,
        'dashboard_url': dashboard_url
    }
    return render(request, 'profile.html', context)

def logout_view(request):
    logout(request)
    return render(request, 'logout.html')

def login_view(request):
    next_url = request.GET.get('next', '')
    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            user = form.get_user()
            if user:
                django_login(request, user)
                if next_url:
                    return redirect(next_url)
                return redirect('quiz_master_dashboard' if user.is_quiz_master else 'quiz_taker_dashboard')
            else:
                form.add_error(None, 'Invalid registration number or password.')
    else:
        form = UserLoginForm()
    return render(request, 'login.html', {'form': form, 'next': next_url})


@login_required
def change_password_view(request):
    if request.method == 'POST':
        form = ChangePasswordForm(request.POST)
        if form.is_valid():
            old_password = form.cleaned_data['old_password']
            new_password1 = form.cleaned_data['new_password1']

            if request.user.check_password(old_password):
                request.user.set_password(new_password1)
                request.user.save()
                messages.success(request, 'Password changed successfully.')
                return redirect('profile')
            else:
                form.add_error('old_password', 'Current password is incorrect.')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = ChangePasswordForm()

    return render(request, 'change_password.html', {'form': form})

# Quiz creation, editing, and deletion views
@login_required
def create_quiz_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            title = data.get('title')
            description = data.get('description')
            time_limit = int(data.get('time_limit'))

            quiz = Quiz.objects.create(
                uuid=uuid.uuid4(),
                title=title,
                description=description,
                created_by=request.user,
                time_limit=time_limit,
                total_score=0.0
            )

            questions = data.get('questions', [])
            for index, question_data in enumerate(questions):
                try:
                    mark = float(question_data['mark'])
                except ValueError:
                    return JsonResponse({"error": "Invalid mark format"}, status=400)

                Question.objects.create(
                    quiz=quiz,
                    type=question_data['type'],
                    content=question_data['content'],
                    mcq_option1=question_data.get('mcq_option1', ''),
                    mcq_option2=question_data.get('mcq_option2', ''),
                    mcq_option3=question_data.get('mcq_option3', ''),
                    mcq_option4=question_data.get('mcq_option4', ''),
                    correct_answer=question_data.get('correct_answer', ''),
                    keywords=question_data.get('keywords', ''),
                    mark=mark,
                    created_by=request.user,
                    position=index
                )

            quiz.update_total_score()
            return JsonResponse({'message': 'Quiz created successfully'}, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        except KeyError as e:
            return JsonResponse({"error": f"Missing field: {str(e)}"}, status=400)
        except Exception as e:
            logger.exception("An error occurred during quiz creation")
            return JsonResponse({"error": f"Error: {str(e)}"}, status=400)

    return render(request, 'create_quiz.html')


@login_required
def edit_quiz_view(request, quiz_uuid):
    quiz = get_object_or_404(Quiz, uuid=quiz_uuid)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            quiz.title = data.get('title', quiz.title)
            quiz.description = data.get('description', quiz.description)
            quiz.time_limit = int(data.get('time_limit', quiz.time_limit))
            quiz.save()

            # Delete all existing questions associated with this quiz
            quiz.questions.all().delete()

            # Get the list of new questions from the form data
            questions = data.get('questions', [])

            for index, question_data in enumerate(questions):
                try:
                    mark = float(question_data['mark']) if question_data['mark'] is not None else 0.0
                except (ValueError, TypeError):
                    return JsonResponse({"error": "Invalid mark format"}, status=400)

                # Create new question entries
                Question.objects.create(
                    quiz=quiz,
                    type=question_data['type'],
                    content=question_data['content'],
                    mcq_option1=question_data.get('mcq_option1', ''),
                    mcq_option2=question_data.get('mcq_option2', ''),
                    mcq_option3=question_data.get('mcq_option3', ''),
                    mcq_option4=question_data.get('mcq_option4', ''),
                    correct_answer=question_data.get('correct_answer', ''),
                    keywords=question_data.get('keywords', ''),
                    mark=mark,
                    created_by=request.user,
                    position=index
                )

            # Recalculate the total score for the quiz
            quiz.update_total_score()

            return JsonResponse({'message': 'Quiz updated successfully'}, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        except KeyError as e:
            return JsonResponse({"error": f"Missing field: {str(e)}"}, status=400)
        except Exception as e:
            logger.exception("An error occurred during quiz editing")
            return JsonResponse({"error": f"Error: {str(e)}"}, status=400)

    # Fetch all the questions for the quiz and sort them by position
    questions = Question.objects.filter(quiz=quiz).order_by('position')
    return render(request, 'edit_quiz.html', {'quiz': quiz, 'questions': questions})



@login_required
def delete_quiz_view(request, quiz_uuid):
    quiz = get_object_or_404(Quiz, uuid=quiz_uuid, created_by=request.user)
    quiz.delete()
    return redirect('quiz_management')

# Quiz access, submission, and analytics views
@login_required (login_url='/login/')
def quiz_access_and_submit_view(request, quiz_uuid=None):
    if request.method == 'POST':
        if 'answers' in request.POST and quiz_uuid:
            try:
                quiz = get_object_or_404(Quiz, uuid=quiz_uuid)

                answers = json.loads(request.POST.get('answers', '[]'))
                total_score = 0
                results = []

                with transaction.atomic():
                    for answer_data in answers:
                        question_id = answer_data.get('question_id')
                        user_answer = answer_data.get('answer')

                        question = get_object_or_404(Question, id=question_id, quiz=quiz)

                        correct_answer = question.correct_answer

                        if question.type == 'SA':
                            # Use NLP to get detailed feedback and determine correctness
                            is_correct, feedback = detailed_feedback(user_answer, correct_answer, question.keywords)
                            score = question.mark if is_correct else 0
                        elif question.type == 'TF':
                            is_correct = (user_answer == correct_answer)
                            score = question.mark if is_correct else 0
                            feedback = ["Correct" if is_correct else "Incorrect"]
                        else:  # MCQ
                            is_correct = (user_answer == correct_answer)
                            score = question.mark if is_correct else 0
                            feedback = ["Correct" if is_correct else "Incorrect"]

                        Answer.objects.create(
                            user=request.user,
                            quiz=quiz,
                            question=question,
                            answer=user_answer,
                            is_correct=is_correct,
                            feedback=' '.join(feedback)
                        )

                        total_score += score
                        results.append({
                            'question_id': question_id,
                            'is_correct': bool(is_correct),  # Convert to JSON-serializable type
                            'score': score,
                            'feedback': feedback
                        })

                    result, created = Result.objects.get_or_create(user=request.user, quiz=quiz,
                                                                   defaults={'score': 0, 'completion_status': ''})
                    result.score = total_score
                    result.completion_status = 'Completed'
                    result.save()

                return redirect('quiz_result', quiz_uuid=quiz.uuid)
            except json.JSONDecodeError:
                return JsonResponse({"error": "Invalid JSON"}, status=400)
            except KeyError as e:
                return JsonResponse({"error": f"Missing field: {str(e)}"}, status=400)
            except IntegrityError as e:
                logger.exception("Foreign key constraint failed")
                return JsonResponse({"error": "Foreign key constraint failed"}, status=400)
            except Exception as e:
                logger.exception("An error occurred during quiz submission")
                return JsonResponse({"error": f"Error: {str(e)}"}, status=400)
        else:
            return JsonResponse({"error": "Invalid request"}, status=400)
    else:
        if quiz_uuid:
            quiz = get_object_or_404(Quiz, uuid=quiz_uuid)
            result = Result.objects.filter(user=request.user, quiz=quiz).first()
            if result:
                answers = Answer.objects.filter(quiz=quiz, user=request.user)
                questions = [{
                    'text': answer.question.content,
                    'user_answer': answer.answer,
                    'is_correct': answer.is_correct,
                    'correct_answer': answer.question.correct_answer,
                    'feedback': answer.feedback
                } for answer in answers]

                result.correct_count = answers.filter(is_correct=True).count()
                result.incorrect_count = answers.filter(is_correct=False).count()
                result.unanswered_count = quiz.questions.count() - answers.count()

                return render(request, 'quiz_already_taken.html', {
                    'quiz': quiz,
                    'result': result,
                    'questions': questions
                })
            questions = Question.objects.filter(quiz=quiz)
            return render(request, 'access_quiz.html', {'quiz': quiz, 'questions': questions})
        else:
            return render(request, 'quiz_taker_dashboard.html')

@login_required
def quiz_confirmation_view(request, quiz_uuid):
    quiz = get_object_or_404(Quiz, uuid=quiz_uuid)
    if request.method == 'POST':
        return redirect('access_quiz', quiz_uuid=quiz_uuid)
    return render(request, 'quiz_confirmation.html', {'quiz': quiz})

@login_required
def quiz_result_view(request, quiz_uuid):
    quiz = get_object_or_404(Quiz, uuid=quiz_uuid)
    result = get_object_or_404(Result, quiz=quiz, user=request.user)

    feedback_data = {
        'quiz': quiz,
        'result': result,
        'questions': []
    }

    answers = Answer.objects.filter(quiz=quiz, user=request.user)
    for answer in answers:
        feedback_data['questions'].append({
            'text': answer.question.content,
            'user_answer': answer.answer,
            'is_correct': answer.is_correct,
            'correct_answer': answer.question.correct_answer,
            'feedback': answer.feedback
        })

    feedback_data['result'].correct_count = answers.filter(is_correct=True).count()
    feedback_data['result'].incorrect_count = answers.filter(is_correct=False).count()
    feedback_data['result'].unanswered_count = quiz.questions.count() - answers.count()

    return render(request, 'quiz_result.html', feedback_data)

@login_required
def quiz_taker_analytics_view(request):
    user = request.user
    total_attempts = Result.objects.filter(user=user).count()
    correct_answers = Answer.objects.filter(user=user, is_correct=True).count()
    total_questions = Answer.objects.filter(user=user).count()
    average_score = correct_answers / total_questions if total_questions > 0 else 0
    highest_score = Result.objects.filter(user=user).order_by('-score').first()
    lowest_score = Result.objects.filter(user=user).order_by('score').first()
    completion_rate = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
    time_spent_per_quiz = Answer.objects.filter(user=user).values('quiz').annotate(total_time=Sum('time_spent'))
    category_performance = Answer.objects.filter(user=user).values('question__category').annotate(
        total_correct=Sum('is_correct'), total_questions=Count('id'))
    recent_activity = Answer.objects.filter(user=user).order_by('-id')[:10]
    feedback_analysis = Answer.objects.filter(user=user).values('feedback').annotate(
        count=Count('feedback')).order_by('-count')

    return render(request, 'quiz_taker_analytics.html', {
        'total_attempts': total_attempts,
        'correct_answers': correct_answers,
        'average_score': average_score,
        'highest_score': highest_score,
        'lowest_score': lowest_score,
        'completion_rate': completion_rate,
        'time_spent_per_quiz': time_spent_per_quiz,
        'category_performance': category_performance,
        'recent_activity': recent_activity,
        'feedback_analysis': feedback_analysis,
    })

@login_required
def quiz_master_analytics_view(request):
    user = request.user
    total_quizzes = Quiz.objects.filter(created_by=user).count()
    total_questions = Question.objects.filter(quiz__created_by=user).count()
    total_attempts = Result.objects.filter(quiz__created_by=user).count()
    average_score = Result.objects.filter(quiz__created_by=user).aggregate(avg_score=Avg('score'))['avg_score'] or 0
    highest_score = Result.objects.filter(quiz__created_by=user).aggregate(max_score=Max('score'))['max_score'] or 0
    lowest_score = Result.objects.filter(quiz__created_by=user).aggregate(min_score=Min('score'))['min_score'] or 0
    completion_rate = (Result.objects.filter(quiz__created_by=user, completion_status='Completed').count() / total_attempts * 100) if total_attempts > 0 else 0
    time_spent_per_quiz = Answer.objects.filter(quiz__created_by=user).values('quiz').annotate(total_time=Sum('time_spent'))
    category_performance = Answer.objects.filter(quiz__created_by=user).values('question__category').annotate(
        total_correct=Sum('is_correct'), total_questions=Count('id'))
    recent_activity = Result.objects.filter(quiz__created_by=user).order_by('-id')[:10]
    feedback_analysis = Result.objects.filter(quiz__created_by=user).values('feedback').annotate(
        count=Count('feedback')).order_by('-count')

    return render(request, 'quiz_master_analytics.html', {
        'total_quizzes': total_quizzes,
        'total_questions': total_questions,
        'total_attempts': total_attempts,
        'average_score': average_score,
        'highest_score': highest_score,
        'lowest_score': lowest_score,
        'completion_rate': completion_rate,
        'time_spent_per_quiz': time_spent_per_quiz,
        'category_performance': category_performance,
        'recent_activity': recent_activity,
        'feedback_analysis': feedback_analysis,
    })

@login_required
def quiz_performance_analytics_view(request, quiz_uuid):
    quiz = get_object_or_404(Quiz, uuid=quiz_uuid)
    total_questions = quiz.questions.count()
    total_submissions = Result.objects.filter(quiz=quiz).count()
    aggregate_scores = Result.objects.filter(quiz=quiz).aggregate(
        average=Avg('score'),
        highest=Max('score'),
        lowest=Min('score')
    )
    average_score = aggregate_scores['average'] or 0
    highest_score = aggregate_scores['highest'] or 0
    lowest_score = aggregate_scores['lowest'] or 0
    completion_count = Result.objects.filter(quiz=quiz, completion_status='Completed').count()
    completion_rate = (completion_count / total_submissions * 100) if total_submissions > 0 else 0

    return render(request, 'quiz_performance_analytics.html', {
        'quiz': quiz,
        'total_questions': total_questions,
        'total_submissions': total_submissions,
        'average_score': average_score,
        'highest_score': highest_score,
        'lowest_score': lowest_score,
        'completion_rate': completion_rate,
    })

@login_required
def quiz_taker_dashboard_view(request):
    user = request.user
    search_query = request.GET.get('search', '')

    quizzes_taken = Result.objects.filter(user=user)

    if search_query:
        quizzes_taken = quizzes_taken.filter(Q(quiz__title__icontains=search_query))

    total_quizzes = quizzes_taken.count()

    if total_quizzes > 0:
        average_score = sum(result.score_percentage for result in quizzes_taken) / total_quizzes
    else:
        average_score = 0

    average_score = float(f"{average_score:.3g}")

    recent_activity = quizzes_taken.order_by('-created_at')[:5]

    context = {
        'user': user,
        'quizzes_taken': quizzes_taken,
        'total_quizzes': total_quizzes,
        'average_score': round(average_score, 2),
        'recent_activity': recent_activity,
        'search_query': search_query,
    }

    return render(request, 'quiz_taker_dashboard.html', context)

@login_required
def quiz_management_view(request):
    if request.method == 'POST':
        quiz_uuid = request.POST.get('delete')
        if quiz_uuid:
            quiz = get_object_or_404(Quiz, uuid=quiz_uuid, created_by=request.user)
            quiz.delete()
        return redirect('quiz_management')

    search_query = request.GET.get('search', '')
    quizzes = Quiz.objects.filter(created_by=request.user)

    if search_query:
        quizzes = quizzes.filter(title__icontains=search_query)

    quizzes_data = []

    for quiz in quizzes:
        num_questions = quiz.questions.count()
        quizzes_data.append({
            'quiz': quiz,
            'num_questions': num_questions
        })

    return render(request, 'quiz_management.html', {'quizzes_data': quizzes_data, 'search_query': search_query})

@login_required
def update_profile_view(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = UserProfileForm(instance=request.user)
    return render(request, 'update_profile.html', {'form': form})

@login_required
def available_quizzes_view(request):
    quizzes = Quiz.objects.filter(parent_quiz__isnull=True)
    return render(request, 'available_quizzes.html', {'quizzes': quizzes})

@login_required
def quizzes_taken_view(request):
    quizzes_taken = Result.objects.filter(user=request.user)
    return render(request, 'quizzes_taken.html', {'quizzes_taken': quizzes_taken})

@login_required (login_url='/login/')
def quiz_confirmation_view(request, quiz_uuid):
    quiz = get_object_or_404(Quiz, uuid=quiz_uuid)
    if request.method == 'POST':
        return redirect('access_quiz', quiz_uuid=quiz_uuid)
    return render(request, 'quiz_confirmation.html', {'quiz': quiz})


@login_required
def quiz_result_view(request, quiz_uuid):
    quiz = get_object_or_404(Quiz, uuid=quiz_uuid)
    result = get_object_or_404(Result, quiz=quiz, user=request.user)

    feedback_data = {
        'quiz': quiz,
        'result': result,
        'questions': []
    }

    answers = Answer.objects.filter(quiz=quiz, user=request.user)
    for answer in answers:
        feedback_data['questions'].append({
            'text': answer.question.content,
            'user_answer': answer.answer,
            'is_correct': answer.is_correct,
            'correct_answer': answer.question.correct_answer,
            'feedback': answer.feedback
        })

    feedback_data['result'].correct_count = answers.filter(is_correct=True).count()
    feedback_data['result'].incorrect_count = answers.filter(is_correct=False).count()
    feedback_data['result'].unanswered_count = quiz.questions.count() - answers.count()

    return render(request, 'quiz_result.html', feedback_data)

@login_required
def quiz_results_view(request, quiz_uuid):
    quiz = get_object_or_404(Quiz, uuid=quiz_uuid)
    results = Result.objects.filter(quiz=quiz).select_related('user')

    context = {
        'quiz': quiz,
        'results': results
    }
    return render(request, 'quiz_results.html', context)

@login_required
def quiz_performance_chart_view(request, quiz_uuid):
    quiz = get_object_or_404(Quiz, uuid=quiz_uuid)
    results = Result.objects.filter(quiz=quiz)

    score_ranges = ['0-10', '11-20', '21-30', '31-40', '41-50', '51-60', '61-70', '71-80', '81-90', '91-100']
    score_data = {range_label: 0 for range_label in score_ranges}

    for result in results:
        score_percentage = (result.score / quiz.total_score) * 100
        if score_percentage <= 10:
            score_data['0-10'] += 1
        elif score_percentage <= 20:
            score_data['11-20'] += 1
        elif score_percentage <= 30:
            score_data['21-30'] += 1
        elif score_percentage <= 40:
            score_data['31-40'] += 1
        elif score_percentage <= 50:
            score_data['41-50'] += 1
        elif score_percentage <= 60:
            score_data['51-60'] += 1
        elif score_percentage <= 70:
            score_data['61-70'] += 1
        elif score_percentage <= 80:
            score_data['71-80'] += 1
        elif score_percentage <= 90:
            score_data['81-90'] += 1
        else:
            score_data['91-100'] += 1

    data = {
        'labels': score_ranges,
        'values': list(score_data.values())
    }

    return JsonResponse(data)

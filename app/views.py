from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response
from django.shortcuts import get_object_or_404
from django.template import RequestContext
from django.contrib.auth import logout
from django.http import HttpResponseRedirect, HttpResponse
from tomcookery.app.models import *
from tomcookery.app.forms import *
from .forms import ProfileForm
from django.conf import settings
import Image
import datetime
from django.core.files.base import ContentFile
import sys
sys.path.append("/Users/corygwin/djangoenv/lib/python2.6/site-packages/PIL-1.1.7-py2.6-macosx-10.3-fat.egg")

response_data = { 'app_name': 'Recipe Wars', 'MEDIA_URL': settings.MEDIA_URL }

def index(request):
	response_data.update({'moretoprecipes': Recipe.objects.all().order_by('-votes')[1:12] })
	response_data.update({'toprecipe': Recipe.objects.all().order_by('-votes')[0:1] })
	return render_to_response('index.html',
                              response_data,
                              context_instance = RequestContext(request))

def recipe(request, recipe_url):
	curRecipe = get_object_or_404(
		Recipe,
		url=recipe_url
	)
	ingredients = Ingredient_Measurement.objects.filter(hrecipe=curRecipe)
	response_data.update({'recipe':curRecipe,"ingredients":ingredients})
	return render_to_response('recipe.html',
                              response_data,
                              context_instance = RequestContext(request))

@login_required
def recipe_vote(request):
	'Recipe voting'
	if 'id' in request.GET:
		try:
			recipe_id = request.GET['id']
			recipe = Recipe.objects.get(id=recipe_id)
			user_voted = recipe.users_voted.filter(
				username = request.user.username
			)
			if not user_voted:
				recipe.votes += 1
				recipe.users_voted.add(request.user)
				recipe.save()
		except Recipe.DoesNotExist:
			raise Http404('Recipe Not Found')
	if 'HTTP_REFERER' in request.META:
		return HttpResponseRedirect(request.META['HTTP_REFERER'])
	return HttpResponseRedirect('/')
			


def register_page(request):
	if request.method == 'POST':
		form = RegistrationForm(request.POST)
		if form.is_valid():
			user = User.objects.create_user(
				username = form.cleaned_data['username'],
				password = form.cleaned_data['password1'],
				email = form.cleaned_data['email']
			)
			return HttpResponseRedirect('/register/success/')
	else:
		form = RegistrationForm()
	variables = RequestContext(request,{'form':form})
	return render_to_response('registration/register.html',response_data,
                              context_instance = variables)

def logout_page(request):
	logout(request)
	return HttpResponseRedirect('/')

@login_required
def profile(request):
    '''
    Displays page where user can update their profile.
    
    @param request: Django request object.
    @return: Rendered profile.html.
    '''
    if request.method == 'POST':
        form = ProfileForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            print data

            #Update user with form data
            request.user.first_name = data['first_name']
            request.user.last_name = data['last_name']
            request.user.email = data['email']
            request.user.save()

            messages.success(request, 'Successfully updated profile!')
    else: 
        #Try to pre-populate the form with user data.
        form = ProfileForm(initial = {
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
        })

    response_data.update({'form': form, 'user': request.user})
    return render_to_response('profile.html',
                              response_data,
                              context_instance = RequestContext(request))

def _handleImageResize(image):
	path = settings.MEDIA_ROOT+"/"+str(image)
	print path
	im = Image.open(path)
	im.thumbnail((512,512), Image.ANTIALIAS)
	im.save(path)
                             
def _ingredientsProcess(ingString, recipe):
	for set in ingString.split(","):
		amount, ing = set.split(";")
		ingObject, dummy = Ingredient.objects.get_or_create(
			name= ing
		)
		group = Ingredient_Measurement(ingredient=ingObject,hrecipe=recipe,value=amount)
		group.save()
	return recipe
			
@login_required
def submit(request):
    if request.method == 'POST':
        form = recipeNewSaveForm(request.POST,request.FILES)
        if form.is_valid():
			from django.template.defaultfilters import slugify
			recipe = Recipe()
			recipe.name = form.cleaned_data['name']
			recipe.published = datetime.datetime.now()
			recipe.yields = form.cleaned_data['yields']
			recipe.summary = form.cleaned_data['summary']
			recipe.instructions = form.cleaned_data['instructions']
			#recipe.photos = form.cleaned_data['photos']
			recipe.submitor = request.user
			#save the recipe because it needs a key before it can have many to many rels.
			recipe.save()
			# create a url, we will make sure it is unique by adding the id number to the end.
			url = form.cleaned_data['name'] + "-" + str(recipe.id)
			recipe.url = slugify(url)
			recipe.users_voted.add(request.user)
			#file_content = ContentFile(request.FILES['photo'].read())
			try:
				if request.FILES['photo']:
					file = request.FILES['photo']
					photo = Photo.objects.create()
					photo.photo.save(file.name,file)
					photo.hrecipe_set.add(recipe)
					#now that we have the image lets resize it to a decent size
					_handleImageResize(photo.photo)
			except:
				pass
			
			for tagName in form.cleaned_data['tags'].split(","):
				if tagName != None:
					tag, dummy = Tag.objects.get_or_create(name=tagName.strip())
					tag.hrecipe_set.add(recipe)
					tag.save()
            
			durObject, dummy = Duration.objects.get_or_create(
				duration= form.cleaned_data['durations']
			)
			durObject.hrecipe_set.add(recipe)
			durObject.save()
			recipe = _ingredientsProcess(form.cleaned_data['ingredients'].rstrip('\n'), recipe)
            #ingredients = form.cleaned_data['ingredient'].split()
            #for ingredient in ingredients:
                #ingredientholder, dummy = recipe.objects.get_or_create(ingredients=ingredient)
                #Ingredient.tag_set.add(ingredientholder)
			recipe.save()
			redirectTo = "/recipes/recipe/%s" % recipe.url 
			return HttpResponseRedirect(redirectTo)
    else:
        form = recipeNewSaveForm()
    variables = RequestContext(request, {
        'form': form
    })
    
    return render_to_response('submit.html', response_data,
                              context_instance = variables)


def ajax_tag_autocompletion(request):
	"tag parameter term and returns 10 tags that start with the query"
	if 'term' in request.GET:
		from django.utils import simplejson
		tags = Tag.objects.filter(
			name__istartswith = request.GET['term']
		)[:10]
		results = [ x.name for x in tags ]
		#print(results)
		resp = simplejson.dumps(results)
		return HttpResponse(resp, mimetype='application/json')
	return HttpResponse()
	
def ajax_ingredient_autocompletion(request):
	"tag parameter term and returns 10 tags that start with the query"
	if 'term' in request.GET:
		from django.utils import simplejson
		tags = Ingredient.objects.filter(
			name__istartswith = request.GET['term']
		)[:10]
		results = [ x.name for x in tags ]
		#print(results)
		resp = simplejson.dumps(results)
		return HttpResponse(resp, mimetype='application/json')
	return HttpResponse()
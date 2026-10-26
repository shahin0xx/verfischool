## Face recognition project (face detection, face recognition) with the Django framework.

In this project, the  ``dlib`` library has been used in a custom way.
Generally, it receives images separately, then recognizes each form and compares it with the database model, and I can separate unknown and recognized items and even save their images in separate folders...

To receive images from two cameras simultaneously and optimize resources, the ``Threading`` library has been used.

And `` celery`` has also been used to record images simultaneously, which you can enable from the ‍`views.py` and `settings.py` files if needed.

# The algorithm has an accuracy of 98.86 You can see part of the algorithm in the following link to better understand it:

ref : https://medium.com/@ageitgey/machine-learning-is-fun-part-4-modern-face-recognition-with-deep-learning-c3cffc121d78

You can receive images from two cameras at the same time. To set it up, refer to the following file:`` verifi/camera.py ``

And to view the output of the camera views: `` 127.0.0.1:8000/stream ``


To create a new model (for people who are going to be recognized), follow this address:‍‍`` ‍1‍2‍7.0.0.1/createModel ``

First, it receives specifications such as name or ID for the user from you, then to receive the model's photo, there are two solutions. First, get the saved photo. Second, take a photo from the camera.

To set the camera address to take a picture, you can set the address in the `picture.py` file.

Also, get a log every 5 seconds with the address ` 127.0.0.1:8000/log ‍‍`.

Then you can use `127.0.0.1:8000/admin` to view all logs and results or built models or to edit and delete.



You can also use Docker with the following commands:

## RUN

__sudo docker-compose up__


## OR

__pyhon3 manage.py runserver__

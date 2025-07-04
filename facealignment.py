import numpy as np
import matplotlib.pyplot as plt
import cv2
from sklearn import linear_model
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split

# Useful functions
def visualise_pts(img, pts):
    plt.imshow(img, cmap='gray')
    plt.plot(pts[:, 0], pts[:, 1], '+r')
    plt.show()

def visualise_3pts(img, pts, pts2, pts3):
    plt.imshow(img, cmap='gray')
    plt.plot(pts[:, 0], pts[:, 1], '+r')
    plt.plot(pts2[:, 0], pts2[:, 1], '+g')
    plt.plot(pts3[:, 0], pts3[:, 1], '+b')
    plt.show()

def euclid_dist(pred_pts, gt_pts):
    """
    Calculate the euclidean distance between pairs of points
    :param pred_pts: The predicted points
    :param gt_pts: The ground truth points
    :return: An array of shape (no_points,) containing the distance of each predicted point from the ground truth
    """
    import numpy as np
    pred_pts = np.reshape(pred_pts, (-1, 2))
    gt_pts = np.reshape(gt_pts, (-1, 2))
    return np.sqrt(np.sum(np.square(pred_pts - gt_pts), axis=-1))

def save_as_csv(points, location = '.'):
    """
    Save the points out as a .csv file
    :param points: numpy array of shape (no_test_images, no_points, 2) to be saved
    :param location: Directory to save results.csv in. Default to current working directory
    """
    assert points.shape[0]==554, 'wrong number of image points, should be 554 test images'
    assert np.prod(points.shape[1:])==5*2, 'wrong number of points provided. There should be 5 points with 2 values (x,y) per point'
    np.savetxt(location + '/results_task2.csv', np.reshape(points, (points.shape[0], -1)), delimiter=',')

# Load the train data using np.load
train_data = np.load('face_alignment_training_images.npz', allow_pickle=True)

# Extract the training images and points
train_images = train_data['images']
train_points = train_data['points']

# Load the test data
test_data = np.load('face_alignment_test_images.npz', allow_pickle=True)

# Extract the testing images
test_images = test_data['images']

# Preprocess an array of images
def preprocess(images, scale):
    preprocess_images = []
    for img in images:
        # Resize the image to the new scale
        resized_img = cv2.resize(img, [int(img.shape[0] * scale), int(img.shape[1] * scale)])
        # Convert to greyscale
        greyscaled_img = cv2.cvtColor(resized_img, cv2.COLOR_RGB2GRAY)

        preprocess_images.append(greyscaled_img)
    return np.array(preprocess_images)

# Resize an array of points by the scale
def resize_points(pointsArr, scale):
    resized_pointsArr = []
    for points in pointsArr:
        resized_pointsArr.append(points[:,:] * scale)
    return np.array(resized_pointsArr)

resize_scale = 0.25 # Used for all images and points

# Preprocess the train and test images
train_images_preprocessed = preprocess(train_images, resize_scale)
test_images_preprocessed = preprocess(test_images, resize_scale)

# Then resize the train points to match the new image size
train_points_resized = resize_points(train_points, resize_scale)

# Find the average of all the training points for initial SIFT descriptor keypoints
average_points = np.mean(train_points_resized, axis=0)
print("average points:\n", average_points)

# create sift object
sift = cv2.SIFT_create()

def compute_descriptors(image, points):
    # Use a keypoint size going of original 256x256 image size, then scale it
    keypoint_size = 10 * resize_scale
    keypoints = [cv2.KeyPoint(float(x), float(y), keypoint_size) for (x, y) in points]
    # Use sift.compute at the keypoint
    keypoints, descriptors = sift.compute(image, keypoints)  
    return descriptors

def cascaded_regression(num_regressors, damping_factors, train_images, train_points):
    num_images = len(train_images)
    predicted_train_points = [None] * num_images
    regressors = []

    for i in range(num_regressors):
        x_train, y_train = [], []

        for j in range(num_images):
            img = train_images[j]

            # If no previous prediction, use average points as intial prediction
            if predicted_train_points[j] is None:
                predicted_train_points[j] = average_points.copy()
            
            # Compute SIFT descriptors based on the current prediction
            descriptors = compute_descriptors(img, predicted_train_points[j])
            delta = (train_points[j] - predicted_train_points[j]).flatten()

            x_train.append(descriptors.flatten())
            y_train.append(damping_factors[i] * delta)

        x_train = np.array(x_train) # make sure they are np arrays to avoid errors
        y_train = np.array(y_train)

        # Train a linear regression model using the descriptors as input and delta value as target
        model = linear_model.LinearRegression()
        model.fit(x_train, y_train)
        regressors.append(model) # Then append to the list of regressors

        # Now update predictions for all images
        for k in range(num_images):
            img = train_images[k]
            descriptors = compute_descriptors(img, predicted_train_points[k])

            x_feat = descriptors.flatten().reshape(1, -1) # make sure to reshape 
            delta = model.predict(x_feat).reshape(-1, 2)

            # Update prediction using model output and dampening factor
            predicted_train_points[k] = predicted_train_points[k] + damping_factors[i] * delta

    return regressors

def regression_predict(images, regressors, damping_factors):
    predictions = []
    for img in images:
        predicted_points = average_points.copy()
        # Loop through model iterations and refine the predicted points
        for i in range(len(regressors)):
            regressor = regressors[i]
            descriptors = compute_descriptors(img, predicted_points)

            x_feat = descriptors.flatten().reshape(1, -1)
            delta = regressor.predict(x_feat).reshape(-1, 2)

            # increment by delta value 
            predicted_points = predicted_points + damping_factors[i] * delta

        predictions.append(predicted_points)
    
    return(np.array(predictions))

# Get a train/test split
train_images_split, test_images_split, train_points_split, test_points_split = train_test_split(
    train_images, train_points, test_size=0.2, random_state=69
)

# Preprocess and resize all images and points
train_imgs_split_preprocessed = preprocess(train_images_split, resize_scale)
train_pts_split_resized = resize_points(train_points_split, resize_scale)
test_imgs_split_preprocessed = preprocess(test_images_split, resize_scale)
test_pts_split_resized = resize_points(test_points_split, resize_scale)

num_regressors = 5
damping_factors = np.linspace(1.0, 0.1, num_regressors).tolist()
print("damping factors:", damping_factors)

# run cascaded regression with the train/test split
regressors = cascaded_regression(num_regressors, damping_factors, train_imgs_split_preprocessed, train_pts_split_resized)
predictions = regression_predict(test_imgs_split_preprocessed, regressors, damping_factors)
print("predictions shape:", predictions.shape)

# Calculate distance between the predictions and the ground truth points on the test split
distances = euclid_dist(predictions, test_pts_split_resized)
print("Distances:", distances)

# Calculate the mean squared error
mse = mean_squared_error(test_pts_split_resized.flatten(), predictions.flatten())
print("Mean Squared Error:", mse)

# Final predictions
# run cascaded regression with the full train images and train points
regressors = cascaded_regression(num_regressors, damping_factors, train_images_preprocessed, train_points_resized)
# then get predictions on all test images
test_predictions = regression_predict(test_images_preprocessed, regressors, damping_factors)
print("final predictions shape:", test_predictions.shape)

# Resize the final prediction points back to the original size and save to csv
test_predictions_resized = resize_points(test_predictions, 1 / resize_scale)
save_as_csv(test_predictions_resized)

# finally I can visualise the original size predictions with the original test images
for i in range(10):
    idx = np.random.randint(0, test_images.shape[0])
    visualise_pts(test_images[idx], test_predictions_resized[idx])
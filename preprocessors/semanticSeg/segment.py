import csv, torch, numpy, scipy.io, torchvision.transforms
from flask import Flask, request, jsonify
import json
import time
import jsonschema
import logging
import base64
import cv2
import numpy as np
from mit_semseg.models import ModelBuilder, SegmentationModule
from mit_semseg.utils import colorEncode


app = Flask(__name__)

#assigns different colors to different segments. This helps in determining contour or different segments. Refer Line 136 to see how unique color helps in contour determination
colors = scipy.io.loadmat('data/color150.mat')['colors']
names = {}
with open('data/object150_info.csv') as f:
    reader = csv.reader(f)
    next(reader)
    for row in reader:
        names[int(row[0])] = row[5].split(";")[0]
        

#Removes the remaining segments and only highlights the segment of interest with a particular color.
def visualize_result(img, pred, index=None):
    if index is not None:
        pred = pred.copy()
        pred[pred != index] = -1
    pred_color = colorEncode(pred, colors).astype(numpy.uint8)
    nameofobj = names[index+1]
    return pred_color, nameofobj

#takes the colored segment(determined in visualise_reslt function and compressed the segment to 100 pixels
def findContour(pred_color,width,height):
  image = pred_color
  dummy = pred_color.copy()
  gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
  ret, thresh = cv2.threshold(gray_image, 10, 255, cv2.THRESH_BINARY)
  contours, hierarchy = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
  cv2.drawContours(image, contours, -1, (0, 255, 0), 2)
  image = image-dummy
  gray_contour = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
  M = cv2.moments(contours[0])
  centres = []
  area = []
  send = []
  totArea = 0
  for i in range(len(contours)):
    moments = cv2.moments(contours[i])
    if(moments['m00']==0):
      continue
    if cv2.contourArea(contours[i]) < 2000:
      continue
    totArea = totArea + cv2.contourArea(contours[i])
    area.append(cv2.contourArea(contours[i]))
    centres.append((int(moments['m10']/moments['m00']), int(moments['m01']/moments['m00'])))
  max_value = max(area)
  cv2.circle(image, centres[area.index(max_value)], 20, (0, 0, 255), -1)
  centre1 = centres[area.index(max_value)][0]/width
  centre2 = centres[area.index(max_value)][1]/height
  centre = [centre1,centre2]
  nonzero = cv2.findNonZero(gray_contour)
  divide = len(nonzero)/100
  divide = int(divide)
  for i in range(len(nonzero)):
    if(i%divide!=0):
      gray_contour[nonzero[i][0][1]][nonzero[i][0][0]] = 0
  totArea = totArea/(width*height)
  result = cv2.findNonZero(gray_contour)
  for i in range(len(result)):
          send.append([float((result[i][0][1])/height), float((result[i][0][0])/width)])
  return send , centre , totArea


@app.route("/preprocessor", methods=['POST', 'GET'])
def segment():
  dictionary = []
  with open('./schemas/preprocessors/segmentation.schema.json') as jsonfile:
      data_schema = json.load(jsonfile)
  with open('./schemas/preprocessor-response.schema.json') as jsonfile:
      schema = json.load(jsonfile)
  with open('./schemas/definitions.json') as jsonfile:
      definitionSchema = json.load(jsonfile)
  schema_store = {
  schema['$id']: schema,
  definitionSchema['$id']: definitionSchema
  }
  resolver = jsonschema.RefResolver.from_schema(
  schema, store=schema_store)
  net_encoder = ModelBuilder.build_encoder(
      arch='resnet50dilated',
      fc_dim=2048,
      weights='encoder_epoch_20.pth')
  net_decoder = ModelBuilder.build_decoder(
      arch='ppm_deepsup',
      fc_dim=2048,
      num_class=150,
      weights='decoder_epoch_20.pth',
      use_softmax=True)
  crit = torch.nn.NLLLoss(ignore_index=-1)
  segmentation_module = SegmentationModule(net_encoder, net_decoder, crit)
  segmentation_module.eval()
  segmentation_module.cuda()
  pil_to_tensor = torchvision.transforms.Compose([
      torchvision.transforms.ToTensor(),
      torchvision.transforms.Normalize(
          mean=[0.485, 0.456, 0.406],
          std=[0.229, 0.224, 0.225]) 
  ])
  content = request.get_json()
  request_uuid = content["request_uuid"]
  timestamp = time.time()
  preprocessorName = "ca.mcgill.a11y.image.preprocessor.semanticSegmentation"
  url = content["image"]
  image_b64 = url.split(",")[1]
  binary = base64.b64decode(image_b64)
  image = np.asarray(bytearray(binary), dtype="uint8")
  pil_image = cv2.imdecode(image, cv2.IMREAD_COLOR)
  height,width, channels = pil_image.shape
  img = pil_image    
  img_original = numpy.array(img)
  img_data = pil_to_tensor(img)
  img_data = img_data.cuda()
  singleton_batch = {'img_data': img_data[None]}
  output_size = img_data.shape[1:]
  with torch.no_grad():
      scores = segmentation_module(singleton_batch, segSize=output_size)
  _, pred = torch.max(scores, dim=1)
  pred = pred.cpu()[0].numpy()
  color,name = visualize_result(img_original, pred,0)
  predicted_classes = numpy.bincount(pred.flatten()).argsort()[::-1]
  for c in predicted_classes[:5]:
      color,name = visualize_result(img_original, pred, c)
      send, center, area = findContour(color,width,height)
      dictionary.append({"nameOfSegment":name,"coord":send, "centroid":center, "area":area})
  segment = {"segments":dictionary}

  try:
      validator = jsonschema.Draft7Validator(data_schema, resolver=resolver)
      validator.validate(segment)
  except jsonschema.exceptions.ValidationError as e:
      logging.error(e)
      return jsonify("Invalid Preprocessor JSON format"), 500
  response = {
            "request_uuid": request_uuid,
            "timestamp": int(timestamp),
            "name": preprocessorName,
            "data": segment
  }
  try:
      validator = jsonschema.Draft7Validator(schema, resolver=resolver)
      validator.validate(response)
  except jsonschema.exceptions.ValidationError as e:
      logging.error(e)
      return jsonify("Invalid Preprocessor JSON format"), 500

  return response
  

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
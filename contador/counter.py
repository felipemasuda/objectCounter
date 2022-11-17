import cv2
import paho.mqtt.client as mqtt
import threading
import json
import time
import base64
import numpy as np
import os
import configparser

class counter():
    def __init__(self):
        # Paths used on this project
        self.rootPath = os.getcwd()
        self.settingsPath = os.path.join(self.rootPath, 'settings')
        self.backgroundImagePath = os.path.join(self.settingsPath , 'background.png')
        self.tempImagePath = os.path.join(self.settingsPath , 'temp.png')
        # Setting up camera device
        self.capture = cv2.VideoCapture('/dev/video0', cv2.CAP_V4L2)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('M', 'J', 'P', 'G'))
        self.capture.set(cv2.CAP_PROP_FPS, 60)

        #Para simular
        # self.capture = cv2.VideoCapture(os.path.join(self.rootPath, './Xcte_Zcte.avi'))
        for ct in range(60):
            ret, self.frame = self.capture.read()

        # Variables used
        self.hostIP = '192.168.101.122'
        self.hostPort = 1883
        
        self.mqttTopics = {
            'status': 0,
            'total': 0,
            'parameters': "",
            'imageStream': None,
            'run': 0
        }
        self.ROI = {
            'X0': 0.0,
            'Y0': 0.0,
            'X1': 0.0,
            'Y1': 0.0
            }
        self.objectArea = 0.0
        self.objectAreaTolerance = 0.2
        self.lineThreshouldPercent = 0.5
        self.frame = None
        self.frameIndex = 0
        self.backgroundImage = None

        self.kernel = np.ones((3,3), np.uint8) #Cria elemento estruturante
        self.tracked = []
        self.onTrack = []
        self.trackIndex = 1
        
        self.mutex = threading.Lock()
        runMQTT_thread = threading.Thread(target=self.runMQTT)
        runMQTT_thread.start()   
        self.mqttClient = mqtt.Client()
        self.mqttClient.connect(self.hostIP, self.hostPort)

        self.readSettings()

    def runMQTT(self):
        topicsList = self.mqttTopics.keys()
        for topic in topicsList:
            client = mqtt.Client("PI_" + topic)
            client.connect(self.hostIP, self.hostPort)
            client.subscribe(topic, qos=1)
            client.loop_start()
            client.on_message = self.onMessage
    
    def sendMQTTImage (self, imagePath):
        ret, self.frame = self.capture.read()
        cv2.imwrite(imagePath, self.frame)
        f=open(imagePath, "rb") 
        fileContent = f.read()
        f.close()
        ar = base64.b64encode(fileContent).decode('ascii')
        c = 0
        t = None
        for i in ar:
            if c == 0:
                t = i
            else:    
                t += i
            c+=1
            if c == 500000:
                jMsg = {}
                jMsg['data'] = t
                jMsg['end'] = 0
                self.mqttClient.publish("imageStream", json.dumps(jMsg))
                c=0
        jMsg = {}
        jMsg['data'] = t
        jMsg['end'] = 1
        print('Image sended, with size:', len(ar))
        self.mqttClient.publish("imageStream", json.dumps(jMsg))

    def onMessage(self, client, userdata, message):
        if (message.topic == "status"):
            with self.mutex:
                value = int(message.payload.decode('utf-8'))
                if (value == -1):
                    print(message.topic, ": ", value )
                    self.mqttClient.publish("status", self.mqttTopics['status'])
                    if (self.mqttTopics["run"] == 1):
                        self.mqttClient.publish('total', abs(self.mqttTopics["total"]))
                if (value == -2):
                    print(message.topic, ": ", value )
                    self.sendMQTTImage(self.backgroundImagePath)
                if (value == -3):
                    print(message.topic, ": ", value )
                    self.sendMQTTImage(self.tempImagePath)               

        if (message.topic == "total"):
            value = int(message.payload.decode('utf-8'))
            if (value == 0):
                with self.mutex:
                    self.mqttTopics['total'] = int(message.payload.decode('utf-8'))
                    print(message.topic, ": ", self.mqttTopics['total'])

        if (message.topic == "parameters"):
            with self.mutex:
                self.mqttTopics['parameters'] = message.payload.decode('utf-8')
                self.writeSettings()
                print(message.topic, ": ", self.mqttTopics['parameters'])

        if (message.topic == "run"):
            value = int(message.payload.decode('utf-8'))

            if (value == 1):
                self.mqttTopics['status'] = 2
                self.mqttClient.publish("status", self.mqttTopics['status'])
                if (self.mqttTopics['run'] == 0):
                    self.tracked = []
                    self.onTrack = []
                    self.trackIndex = 1
            if (value == 0 and self.mqttTopics['run'] == 1):
                self.readSettings()
            
            with self.mutex:
                self.mqttTopics['run'] = value
            print(message.topic, ": ", self.mqttTopics['run'])
            
    def readSettings(self):
        filePath = os.path.join(self.settingsPath, 'parameters.cfg')
        print(filePath)
        if os.path.isfile(filePath):
            config = configparser.ConfigParser()
            config.read(filePath)
            if config.has_section('ROI') and config.has_section('object'):
                self.ROI['X0'] = int(config['ROI']['X0'])
                self.ROI['Y0'] = int(config['ROI']['Y0'])
                self.ROI['X1'] = int(config['ROI']['X1'])
                self.ROI['Y1'] = int(config['ROI']['Y1'])
                self.objectArea = int(config['object']['area'])
                self.mqttTopics['status'] = 1
                self.setBackground()
            else:
                self.mqttTopics['status'] = 0
        else:
            self.mqttTopics['status'] = 0
        self.mqttClient.publish("status", self.mqttTopics['status'])
        return

    def writeSettings(self):
        #0= X0, 1= Y0, 2= X1, 3=Y1, 4= area
        value = self.mqttTopics['parameters'].split(',')
        self.ROI['X0'] = int(value[0])
        self.ROI['Y0'] = int(value[1])
        self.ROI['X1'] = int(value[2])
        self.ROI['Y1'] = int(value[3])
        self.objectArea = int(value[4])

        if not os.path.isdir(self.settingsPath):
            os.mkdir(self.settingsPath)
        filePath = os.path.join(self.settingsPath, 'parameters.cfg')
        if os.path.isfile(filePath):
            os.remove(filePath) 

        config = configparser.ConfigParser()
        config.add_section('ROI')
        config.add_section('object')
        config['ROI']['X0'] = str(self.ROI['X0'])
        config['ROI']['Y0'] = str(self.ROI['Y0'])
        config['ROI']['X1'] = str(self.ROI['X1'])
        config['ROI']['Y1'] = str(self.ROI['Y1'])
        config['object']['area'] = str(self.objectArea)

        with open(filePath, 'w') as file:
            config.write(file)
        file.close()
        self.mqttTopics['status'] = 1
        self.mqttClient.publish('status', self.mqttTopics['status'])
        print('Saved!')
        self.setBackground()
        return
    
    def setBackground(self):
        self.backgroundImage = cv2.imread(self.backgroundImagePath)
        self.backgroundImage = self.backgroundImage[self.ROI['Y0']:self.ROI['Y1'], self.ROI['X0']:self.ROI['X1']]
        self.heightBackground, self.widthBackground, _ = self.backgroundImage.shape
        self.lineThreshould = self.widthBackground * self.lineThreshouldPercent
        self.backgroundImage = cv2.cvtColor(self.backgroundImage, cv2.COLOR_BGR2GRAY)
        
    def run(self):
        while True:
            # if 1==1:
            if (((self.mqttTopics['status'] == 1) or (self.mqttTopics['status'] == 2)) and (self.mqttTopics['run'] == 1)):
                startTime = time.time()
                #Captura o frame da camera
                ret, self.frame = self.capture.read() 

                self.frameIndex += 1

                #Recorta a imagem na região de interesse
                self.frame = self.frame[self.ROI['Y0']:self.ROI['Y1'], self.ROI['X0']:self.ROI['X1']] 
                self.frameRender = self.frame.copy()

                #Transforma frame escala de cinza
                grayFrame = cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)  

                #Remove o fundo da imagem
                subtractImage = cv2.subtract(self.backgroundImage, grayFrame) 
                
                # cv2.imshow('ads', subtractImage)
                # cv2.imshow('g', grayFrame)
                # cv2.imshow('f', self.frame)
                # keyCode = cv2.waitKey(1) & 0xFF
                # if keyCode == 27:
                #     break
                # time.sleep(666)
                

                #Binariza a imagem
                subtractImage[subtractImage>0]=255 

                #Aplica erosao morfologica, para remover os ruidos 
                subtractImage = cv2.erode(subtractImage, self.kernel, iterations=15) 

                #Aplica dilatacao morfologica, para recuperar a informacao perdida devido a erosao
                subtractImage = cv2.dilate(subtractImage, self.kernel, iterations=10) 

                #Encontra contornos na imagem
                cnts = cv2.findContours(subtractImage, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE) 
                cnts = cnts[0] if len(cnts) == 2 else cnts[1]

                self.onTrack = []
                for c in cnts:
                    #Transforma contorno em bounding box
                    x,y,w,h = cv2.boundingRect(c) 
                    #Calcula area da bounding box
                    area = w*h 
                    print(area, self.objectArea * self.objectAreaTolerance, self.lineThreshould)
                    #Verifica se a area do contorno é maior do que a previamente configurada
                    if area >= self.objectArea * self.objectAreaTolerance: 
                        #Calcula o baricentro da bounding box
                        centroid = (x + x+w)//2 
                        #Adiciona a bounding box com suas informações na lista
                        self.onTrack.append([x, y, x+w, y+h, centroid, self.frameIndex]) 

                self.track()


                print("TOTAL: {0}\nTrackeds: {1}\nFrame time: {2}\n".format(abs(self.mqttTopics["total"]), len(self.tracked), time.time()-startTime))
                
                # Debug
                cv2.line(self.frameRender, (int(self.lineThreshould), 0), (int(self.lineThreshould), 300), (0, 0, 255), 2)
                label = 'TOTAL: ' + str(abs(self.mqttTopics["total"]))
                t_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_PLAIN, 2, 3)[0]
                xt = int(t_size[0]) 
                yt = int(t_size[1]) + 8
                cv2.rectangle(self.frameRender, (0,0), (xt, yt), (240,240,240), -1)
                cv2.putText(self.frameRender, label, (1, 1 + t_size[1] + 4), cv2.FONT_HERSHEY_PLAIN, 2, (132, 0, 0), 3)
                cv2.imshow('Mask + bboxs', self.frameRender)
                keyCode = cv2.waitKey(1) & 0xFF
                if keyCode == 27:
                    break
            else:
                time.sleep(0.05)

    def track (self):
        # self.onTrack   = [x, y, x+w, y+h, centroid, self.frameIndex]
        # self.tracked   = [x, y, x+w, y+h, centroid, self.frameIndex, self.trackIndex, after line]
        if len(self.tracked) == 0:
            for eachonTrack in self.onTrack:
                self.tracked.append(eachonTrack + [self.trackIndex, eachonTrack[4] > self.lineThreshould])
                self.trackIndex += 1
        else:
            onTrackCopy = self.onTrack.copy()
            checkAppend = False
            popOffset = 0
            newTracked = []
            for count, eachOnTrack in enumerate(self.onTrack):
                for eachtracked in self.tracked:
                    iou = self.boundingBoxIntersection(eachOnTrack[:4], eachtracked[:4]) 
                    if iou > 0.2:
                        print("IOU {0}: {1}".format(eachtracked[6], iou))
                        checkAppend = True
                        #Verifica se o objeto cruzou o centro da imagem e computa o total
                        if (eachtracked[7] == True):
                            if (eachtracked[4] < self.lineThreshould):
                                eachtracked[7] = False
                                self.mqttTopics["total"] -= 1
                                self.mqttClient.publish('total', abs(self.mqttTopics["total"]))
                        else:
                            if (eachtracked[4] > self.lineThreshould):
                                eachtracked[7] = True
                                self.mqttTopics["total"] += 1
                                self.mqttClient.publish('total', abs(self.mqttTopics["total"]))
                        newTracked.append(eachOnTrack + [eachtracked[6], eachtracked[7]] )
                        # Debug imshow
                        font = cv2.FONT_HERSHEY_SIMPLEX
                        fontScale = 1
                        color = (255, 0, 0)
                        thickness = 2
                        cv2.rectangle(self.frameRender, (eachOnTrack[0], eachOnTrack[1]), (eachOnTrack[2], eachOnTrack[3]), (0,255,0), 2)
                        self.frameRender = cv2.putText(self.frameRender, str(eachtracked[6]), (eachOnTrack[0], eachOnTrack[1]+25), font, fontScale, (75,154,160), thickness, cv2.LINE_AA)
                        cv2.circle(self.frameRender, (int(eachOnTrack[4]), int((eachOnTrack[1] + eachOnTrack[3])//2)), 5, color, -1)
                        
                        break
                if (checkAppend):
                    onTrackCopy.pop(count - popOffset)
                    checkAppend = False
                    popOffset += 1
            #Adiciona os novos objetos rastreaveis
            self.tracked = newTracked
            for eachOnTrackCopy in onTrackCopy:
                self.tracked.append(eachOnTrackCopy + [self.trackIndex, eachOnTrackCopy[4] > self.lineThreshould])
                self.trackIndex += 1

    def boundingBoxIntersection(self, boxA, boxB):
        #Determina as coordenadas (x, y) das bounding boxes
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        #Calcula area de intersecao da bounding box
        interArea = abs(max((xB - xA, 0)) * max((yB - yA), 0))
        #Retorna 0 caso nao haja intersecao
        if interArea == 0:
            return 0

        #Calcula as areas das bounding boxes
        boxAArea = abs((boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
        boxBArea = abs((boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))

        #Calcula a porcentagem de intersecao das bounding boxes
        iou = interArea / float(boxAArea + boxBArea - interArea)

        return iou

if __name__ == "__main__":
    obj = counter()
    obj.run()
from PyQt5 import QtCore, QtGui, QtWidgets
import paho.mqtt.client as mqtt
import base64
import json
import os

WIDTH_MARGIN = 100
HEIGHT_MARGIN = 100
WIDTH = 1280 + WIDTH_MARGIN*2
HEIGHT = 720 + HEIGHT_MARGIN*2

class mqttThread(QtCore.QThread):
    statusSignal = QtCore.pyqtSignal(int)
    totalSignal = QtCore.pyqtSignal(int)
    imageStreamEndSignal = QtCore.pyqtSignal(bool)
    runSignal = QtCore.pyqtSignal(bool)

    def __init__(self, cashPath, topicsList, hostIP, hostPort, parent=None):
        super().__init__()
        self.running = 0
        self.cashPath = cashPath
        self.topicsList = topicsList
        self.hostIP = hostIP
        self.hostPort = hostPort
        self.imageStream = None
        self.imageStreamEnd = 0

    def onMessage(self, client, userdata, message):
        if (message.topic == "status"):
            value = int(message.payload.decode('utf-8'))
            if (value > 0):
                self.statusSignal.emit(value)
                print(message.topic, ": ", value)

        if (message.topic == "total"):
            value = int(message.payload.decode('utf-8'))
            self.totalSignal.emit(value)
            print(message.topic, ": ", value)

        if (message.topic == "imageStream"):
            if self.imageStream == None:
                jMsg = json.loads(message.payload.decode('utf-8'))
                self.imageStream = jMsg['data'] 
                self.imageStreamEnd = int(jMsg['end']) 
            else:
                jMsg = json.loads(message.payload.decode('utf-8'))
                self.imageStream += jMsg['data'] 
                self.imageStreamEnd = int(jMsg['end']) 
                if self.imageStreamEnd:
                    image = self.imageStream.encode('ascii')
                    print('Image received, with size:', len(image))
                    self.imageStream = base64.b64decode(image)
                    f=open(os.path.join(self.cashPath, 'pixmap.png'), "wb") 
                    f.write(self.imageStream)
                    f.close()
                    self.imageStream = None
                    self.imageStreamEnd = 0
                    self.imageStreamEndSignal.emit(True)

        if (message.topic == "run"):
            QtCore.QThread.msleep(100) 
            value = int(message.payload.decode('utf-8'))
            if (value == 1):
                self.runSignal.emit(True)
            if (value == 0):
                self.runSignal.emit(False)
            print(message.topic, ": ", value)

    def run(self):
        for topic in self.topicsList:
            client = mqtt.Client("IHM_" + topic)
            client.connect(self.hostIP, self.hostPort)
            client.subscribe(topic, qos=1)
            client.loop_start()
            client.on_message = self.onMessage
            self.running = 1

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        self.cashPath = os.path.join(os.getcwd(), 'cash')
        self.topicsList = ["status", "total", "imageStream", "run"]
        self.hostIP = '192.168.101.122'
        self.hostPort = 1883

        mqttThreadObject = mqttThread(self.cashPath, self.topicsList, self.hostIP, self.hostPort)
        mqttThreadObject.statusSignal.connect(self.handleStatus)
        mqttThreadObject.totalSignal.connect(self.handleTotal)
        mqttThreadObject.imageStreamEndSignal.connect(self.handleImageStreamEnd)
        mqttThreadObject.runSignal.connect(self.handleRun)
        mqttThreadObject.start()   

        self.mqttClient = mqtt.Client()
        self.mqttClient.connect(self.hostIP, self.hostPort)

        MainWindow.setObjectName("MainWindow")
        MainWindow.setWindowTitle("Contador IHM")
        MainWindow.resize(WIDTH, HEIGHT)
        
        self.form = QtWidgets.QWidget()
        self.form.setObjectName("Form")
        self.actualScreenIdx = None
        self.image = None

        self.topLabelObject = None
        self.imageWindow = None
        self.pushButton = None
        self.pushButton_2 = None
        self.pushButton_3 = None

        self.ROIpointX1 = None
        self.ROIpointY1 = None
        self.ROIpointX2 = None
        self.ROIpointY2 = None
        self.ROIdraw = None

        self.OBJpointX1 = None
        self.OBJpointY1 = None
        self.OBJpointX2 = None
        self.OBJpointY2 = None
        self.OBJArea = None

        self.total = 0
        self.status = None
        
        MainWindow.mousePressEvent = self.getPos
        MainWindow.setCentralWidget(self.form)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

        waterMark = QtWidgets.QLabel(MainWindow)
        logoUTFPR = QtGui.QPixmap(os.path.join(self.cashPath, 'utfpr.png'))
        waterMark.setPixmap(logoUTFPR)
        waterMark.setGeometry(QtCore.QRect(WIDTH-195, HEIGHT-75, 190, 70))
        waterMark.setObjectName("logoUTFPR")

        # Tela inicial
        self.screenLoading()

    def handleStatus(self, value):
        self.status = value
        if (value == 0 and self.actualScreenIdx == 0):
            self.screenStatus0()
        if (value == 1 and self.actualScreenIdx == 0):
            self.screenStatus1()
        if (value == 2 and self.actualScreenIdx == 0):
            self.screenOp0()

    def handleTotal(self, value):
        self.total = value
        self.lcdNumber.display(self.total)

    def handleImageStreamEnd(self, value):
        if (value and (self.actualScreenIdx == 4 or self.actualScreenIdx == 3)):
            self.image = QtGui.QPixmap(os.path.join(self.cashPath, 'pixmap.png'))
            rectPainter = QtGui.QPainter(self.image)
            if (self.actualScreenIdx == 4):
                rectPainter.setRenderHint(QtGui.QPainter.Antialiasing)
                rectPainter.setPen(QtGui.QPen(QtCore.Qt.green, 4, QtCore.Qt.SolidLine))
                rectPainter.drawRect(self.ROIdraw[0], self.ROIdraw[1], self.ROIdraw[2] , self.ROIdraw[3]) # xi, yi, xcomp, ycomp
            self.imageWindow.setPixmap(self.image)

    def handleRun(self, value):
        if (value == True and self.actualScreenIdx == 5):
            self.screenOp0()
        if (value == False and self.actualScreenIdx == 5):
            self.screenOp0()

    def clearScreen(self):
        self.form.deleteLater()
        self.form = QtWidgets.QWidget()
        self.form.setObjectName("Form")
        MainWindow.setCentralWidget(self.form)
        self.topLabelObject = None
        self.imageWindow = None
        self.pushButton = None
        self.pushButton_2 = None
        self.pushButton_3 = None     

    def screenLoading(self): #0
        self.actualScreenIdx = 0
        self.clearScreen()
        self.midLabel("Conectando...")
        self.mqttClient.publish("status", -1)
        
    def screenStatus0(self): #1
        self.actualScreenIdx = 1
        self.clearScreen()
        self.topLabel("Configure o dipositivo")
        self.initilizePushButton(["CONFIGURAR"], [3])

    def screenStatus1(self): #2
        self.actualScreenIdx = 2
        self.clearScreen()
        self.topLabel("Selecione a opção desejada")
        self.initilizePushButton(["CONFIGURAR", "OPERAR"], [3, 5])

    def screenConfig0(self): #3
        self.actualScreenIdx = 3
        self.mqttClient.publish("status", -2)
        self.ROIpointX1 = None
        self.ROIpointY1 = None
        self.ROIpointX2 = None
        self.ROIpointY2 = None
        self.clearScreen()
        self.topLabel("Selecione a região de interesse na imagem")
        self.imageShow()
        self.initilizePushButton(["VOLTAR", "LIMPAR", "AVANÇAR"], [0, 3, 4])

    def screenConfig1(self): #4
        self.actualScreenIdx = 4
        self.mqttClient.publish("status", -3)
        self.OBJpointX1 = None
        self.OBJpointY1 = None
        self.OBJpointX2 = None
        self.OBJpointY2 = None
        self.clearScreen()
        self.topLabel("Selecione o objeto a ser contabilizado na imagem")
        self.imageShow()
        self.initilizePushButton(["VOLTAR", "LIMPAR", "FINALIZAR"], [3, 4, 0])

    def screenOp0(self): #5
        self.actualScreenIdx = 5
        self.total = 0
        self.mqttClient.publish("total", self.total)
        self.clearScreen()
        self.topLabel("Contagem em andamento")
        self.lcdNumber = QtWidgets.QLCDNumber(self.form)
        self.lcdNumber.setGeometry(QtCore.QRect(int((WIDTH/2)-(300/2)), int((HEIGHT/2)-80), 300, 160))
        self.lcdNumber.setStyleSheet("font: 12pt \"MS Shell Dlg 2\";")
        self.lcdNumber.setStyleSheet("""QLCDNumber{ background-color: gray; color: red; }""")
        self.lcdNumber.setObjectName("lcdNumber")
        self.lcdNumber.display(self.total)
        if (self.status == 1):
            self.initilizePushButton(["VOLTAR", "LIMPAR", "INICIAR"], [0, 5, 6])
        if (self.status == 2):
            self.initilizePushButton(["VOLTAR", "LIMPAR", "PARAR"], [0, 5, 7])

    def initilizePushButton(self, value, screenIdx):
        buttons = []

        if len(value) >= 1:
            self.pushButton = QtWidgets.QPushButton(self.form)
            self.pushButton.clicked.connect(lambda: self.clickMethod(screenIdx[0]))
            self.pushButton.setStyleSheet("font: 16pt \"MS Shell Dlg 2\";")
            self.pushButton.setText(value[0])
            self.pushButton.setObjectName("pushButton")
            buttons.append(self.pushButton)

        if len(value) >= 2:
            self.pushButton_2 = QtWidgets.QPushButton(self.form)
            self.pushButton_2.clicked.connect(lambda: self.clickMethod(screenIdx[1]))
            self.pushButton_2.setStyleSheet("font: 16pt \"MS Shell Dlg 2\";")
            self.pushButton_2.setText(value[1])
            self.pushButton_2.setObjectName("pushButton_2")
            buttons.append(self.pushButton_2)

        if len(value) >= 3:
            self.pushButton_3 = QtWidgets.QPushButton(self.form)
            self.pushButton_3.clicked.connect(lambda: self.clickMethod(screenIdx[2]))
            self.pushButton_3.setStyleSheet("font: 16pt \"MS Shell Dlg 2\";")
            self.pushButton_3.setText(value[2])
            self.pushButton_3.setObjectName("pushButton_3")
            buttons.append(self.pushButton_3)

        self.pushButtonPosition(buttons)
         
    def clickMethod(self, value):
        print('Clicked button with value: ' + str(value))
        if (value == 0):
            if ((self.actualScreenIdx == 4) and (self.OBJpointX2 != None)):
                #0= X0, 1= Y0, 2= X1, 3=Y1, 4= area
                msg = str(self.ROIpointX1) + "," + str(self.ROIpointY1) + "," + str(self.ROIpointX2) + "," + str(self.ROIpointY2) + "," + str(self.OBJArea)
                print('Parameter sent:', msg)
                self.mqttClient.publish("parameters", msg)
                self.screenLoading()
            if ((self.actualScreenIdx == 3) or (self.actualScreenIdx == 5)):
                self.screenLoading()
        if (value == 1):
            self.screenStatus0()
        if (value == 2):
            self.screenStatus1()
        if (value == 3):
            self.screenConfig0()
        if ((value == 4)):
            if (((self.actualScreenIdx == 3) and (self.ROIpointX2 != None)) or (self.actualScreenIdx == 4)):
                self.screenConfig1()
        if (value == 5):
            self.screenOp0()
        if (value == 6):
            self.mqttClient.publish("run", 1)
            self.screenOp0()
        if (value ==7):
            self.mqttClient.publish("run", 0)
            self.screenOp0()

    def getPos(self , event):
        x = event.pos().x()
        y = event.pos().y() 

        if ((self.imageWindow != None) and (x >= WIDTH_MARGIN) and (y >= HEIGHT_MARGIN)):
            if ((self.actualScreenIdx == 3) and (self.ROIpointX2 == None) or (self.actualScreenIdx == 4) and (self.OBJpointX2 == None)):
                pointRadius = 16
                pointPainter = QtGui.QPainter(self.image)
                pointPainter.setRenderHint(QtGui.QPainter.Antialiasing)
                pointPainter.setPen(QtGui.QPen(QtCore.Qt.red, 4, QtCore.Qt.SolidLine))
                pointPainter.setBrush(QtGui.QBrush(QtCore.Qt.white, QtCore.Qt.SolidPattern))
                pointX = x - WIDTH_MARGIN - pointRadius/2
                pointY = y - HEIGHT_MARGIN - pointRadius/2
                pointPainter.drawEllipse(pointX, pointY, pointRadius, pointRadius) #x, y, raiox, raioy
                pointPainter.end()

                if (self.actualScreenIdx == 3):
                    if (self.ROIpointX1 == None):
                        self.ROIpointX1 = x - WIDTH_MARGIN
                        self.ROIpointY1 = y - HEIGHT_MARGIN
                    else:
                        self.ROIpointX2 = x - WIDTH_MARGIN
                        self.ROIpointY2 = y - HEIGHT_MARGIN

                        rectPainter = QtGui.QPainter(self.image)
                        rectPainter.setRenderHint(QtGui.QPainter.Antialiasing)
                        rectPainter.setPen(QtGui.QPen(QtCore.Qt.red, 4, QtCore.Qt.SolidLine))
                        xf = abs(self.ROIpointX2 - self.ROIpointX1)
                        yf = abs(self.ROIpointY2 - self.ROIpointY1)

                        if (self.ROIpointX1 > self.ROIpointX2):
                            xi = self.ROIpointX2
                            self.ROIpointX1 = self.ROIpointX2
                            self.ROIpointX2 = xi
                            
                        if (self.ROIpointY1 > self.ROIpointY2):
                            yi = self.ROIpointY2
                            self.ROIpointY1 = self.ROIpointY2
                            self.ROIpointY2 = yi

                        # self.OBJArea = (self.ROIpointX2 - self.ROIpointX1) * (self.ROIpointY2 - self.ROIpointY1)
                        
                        rectPainter.drawRect(self.ROIpointX1, self.ROIpointY1, xf , yf) # xi, yi, xcomp, ycomp
                        self.ROIdraw = [self.ROIpointX1, self.ROIpointY1, xf , yf]
                        rectPainter.end()

                if (self.actualScreenIdx == 4):
                    if (self.OBJpointX1 == None):
                        self.OBJpointX1 = x - WIDTH_MARGIN
                        self.OBJpointY1 = y - HEIGHT_MARGIN
                    else:
                        self.OBJpointX2 = x - WIDTH_MARGIN
                        self.OBJpointY2 = y - HEIGHT_MARGIN

                        rectPainter = QtGui.QPainter(self.image)
                        rectPainter.setRenderHint(QtGui.QPainter.Antialiasing)
                        rectPainter.setPen(QtGui.QPen(QtCore.Qt.red, 4, QtCore.Qt.SolidLine))
                        xf = abs(self.OBJpointX2 - self.OBJpointX1)
                        yf = abs(self.OBJpointY2 - self.OBJpointY1)

                        if (self.OBJpointX1 > self.OBJpointX2):
                            xi = self.OBJpointX2
                            self.OBJpointX1 = self.OBJpointX2
                            self.OBJpointX2 = xi
                            
                        if (self.OBJpointY1 > self.OBJpointY2):
                            yi = self.OBJpointY2
                            self.OBJpointY1 = self.OBJpointY2
                            self.OBJpointY2 = yi

                        self.OBJArea = xf * yf
                        rectPainter.drawRect(self.OBJpointX1, self.OBJpointY1, xf , yf) # xi, yi, xcomp, ycomp
                        rectPainter.end()
                    
                self.imageWindow.setPixmap(self.image)
        print(x, y)

    def topLabel(self, value):
        self.topLabelObject = QtWidgets.QLabel(self.form)
        self.topLabelObject.setStyleSheet("font: 20pt \"MS Shell Dlg 2\";")
        self.topLabelObject.setObjectName("topLabel")
        self.topLabelObject.setText(value)
        self.topLabelObject.adjustSize()
        x = int((WIDTH - int(self.topLabelObject.size().width()))/2)
        y = int((HEIGHT_MARGIN/2)) - int(self.topLabelObject.size().height()/2)
        self.topLabelObject.move(x, y)

    def midLabel(self, value):
        self.topLabelObject = QtWidgets.QLabel(self.form)
        self.topLabelObject.setStyleSheet("font: 20pt \"MS Shell Dlg 2\";")
        self.topLabelObject.setObjectName("topLabel")
        self.topLabelObject.setText(value)
        self.topLabelObject.adjustSize()
        x = int((WIDTH - int(self.topLabelObject.size().width()))/2)
        y = int((HEIGHT/2) - int(self.topLabelObject.size().height()/2))
        self.topLabelObject.move(x, y)

    def imageShow(self):
        self.imageWindow = QtWidgets.QLabel(self.form)
        self.image = QtGui.QPixmap(os.path.join(self.cashPath, 'loading.png'))
        self.imageWindow.setPixmap(self.image)
        self.imageWindow.setGeometry(QtCore.QRect(WIDTH_MARGIN, HEIGHT_MARGIN, 1280, 720))
        self.imageWindow.setObjectName("image")

    def ipBox(self):
        self.horizontalLayoutWidget = QtWidgets.QWidget(self.form)
        self.horizontalLayoutWidget.setObjectName("horizontalLayoutWidget")

        self.horizontalLayout = QtWidgets.QHBoxLayout(self.horizontalLayoutWidget)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setObjectName("horizontalLayout")

        self.label = QtWidgets.QLabel(self.horizontalLayoutWidget)
        self.label.setStyleSheet("font: 16pt \"MS Shell Dlg 2\";")
        self.label.setObjectName("label")
        self.label.setText("<html><head/><body><p><span style=\" font-size:16pt; font-weight:600;\">IP: </span></p></body></html>")
        self.horizontalLayout.addWidget(self.label)

        self.label_2 = QtWidgets.QLabel(self.horizontalLayoutWidget)
        self.label_2.setStyleSheet("font: 16pt \"MS Shell Dlg 2\";")
        self.label_2.setObjectName("label_2")
        self.label_2.setText("<html><head/><body><p/><span style=\" font-size:16pt; font-weight:600;\"> </span></p></body></html>")
        self.horizontalLayout.addWidget(self.label_2)

        self.plainTextEdit = QtWidgets.QPlainTextEdit(self.horizontalLayoutWidget)
        self.plainTextEdit.setStyleSheet("font: 16pt \"MS Shell Dlg 2\";")
        self.plainTextEdit.setObjectName("plainTextEdit")

        xSize = 300
        x = int(WIDTH/2)-int(xSize/2)
        ySize = 40
        y = int(HEIGHT/2)-int(ySize/2)

        self.horizontalLayoutWidget.setGeometry(QtCore.QRect(x, y, xSize, ySize))
        self.horizontalLayout.addWidget(self.plainTextEdit)

    def pushButtonPosition(self, listPushButton):
        nListPushButton = len(listPushButton)
        xSize = 200
        ySize = 40

        if nListPushButton > 1:
            xStart = int((WIDTH/2) - ((((xSize * nListPushButton) + ((xSize/2)*(nListPushButton-1))))/2))
        else:
            xStart = int((WIDTH/2) - (xSize/2))

        if (self.actualScreenIdx == 1 or self.actualScreenIdx == 2):
            yStart = int((HEIGHT/2) - (ySize/2))
        else:        
            yStart = int(HEIGHT - (HEIGHT_MARGIN - (HEIGHT_MARGIN-ySize)/2))

        for pbtn in listPushButton:
            pbtn.setGeometry(QtCore.QRect(xStart, yStart, xSize, ySize))
            xStart += int((xSize + (xSize/2)))

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())
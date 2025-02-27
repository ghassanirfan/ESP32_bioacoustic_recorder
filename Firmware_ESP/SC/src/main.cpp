/*
MIT License

Copyright (c) 2024 Ghassan Irfan Nauval Al Althaf

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/

#include <Arduino.h>
#include <WiFi.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <SD.h>
#include <SPI.h>
#include <driver/i2s.h>
#include <ESPmDNS.h>
#include <sys/time.h>
#include <Update.h>



// WiFi credentials
const char* ssid = "YOUR_SSID";
const char* password = "YOUR_PASS";
const char* Record_Name = "ESPREC-01";
const char* firmware_version = "FW_1.4.1_unsigned_locale";
const char* serial_number = "000000011";

// I2S configuration
#define I2S_WS 25
#define I2S_SD 33
#define I2S_SCK 32
#define I2S_PORT I2S_NUM_0


// SD card configuration
#define SD_CS 5

// LED pin
#define LED_PIN 2
bool ledState = false;  // Status LED
unsigned long previousMillis = 0;
const unsigned long blinkInterval = 1000; // Blinking setiap 1 detik (1000 ms)

// File management
File recordingFile;
bool isRecording = false;
const int sampleRate = 48000;
const int bitDepth = 32;
uint64_t totalSamples = 0;

AsyncWebServer server(80);

void startRecording();
void stopRecording();
void recordAudio();
void writeWavHeader(File file, int fileSize);
String listFiles();
void deleteFile(const char* path);
bool renameFile(const char* oldName, const char* newName);

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.begin(115200);

  // Initialize WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");

  // Initialize mDNS
  if (!MDNS.begin(Record_Name)) { 
    Serial.println("Error starting mDNS");
    return;
  }
  Serial.println("mDNS started");
  MDNS.addService("http", "tcp", 80);

  // Initialize SD card
  if (!SD.begin(SD_CS)) {
    Serial.println("Card Mount Failed");
    return;
  }

  // I2S configuration
  i2s_config_t i2sConfig = {
    .mode = i2s_mode_t(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = sampleRate,
    .bits_per_sample = i2s_bits_per_sample_t(bitDepth),
    .channel_format = I2S_CHANNEL_FMT_ONLY_RIGHT,
    .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_I2S | I2S_COMM_FORMAT_I2S_MSB),
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 1024
  };

  i2s_pin_config_t pinConfig = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_SD
  };

  i2s_driver_install(I2S_PORT, &i2sConfig, 0, NULL);
  i2s_set_pin(I2S_PORT, &pinConfig);

  // Set up web server routes
  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request){
    String response = "{\n";
    response += "  \"Device Name\": \"" + String(Record_Name) + "\",\n";
    response += "  \"Firmware Version\": \"" + String(firmware_version) + "\",\n";
    response += "  \"Serial Number\": \"" + String(serial_number) + "\",\n";
    response += "  \"SSID Name\": \"" + String(ssid) + "\"\n";
    response += "}";

    request->send(200, "application/json", response); // Hapus request->send kedua
  });


  server.on("/start", HTTP_GET, [](AsyncWebServerRequest *request){
    startRecording();
    request->send(200, "text/plain", "Recording started");
  });

  server.on("/stop", HTTP_GET, [](AsyncWebServerRequest *request){
    stopRecording();
    request->send(200, "text/plain", "Recording stopped");
  });

  server.on("/list", HTTP_GET, [](AsyncWebServerRequest *request){
    String fileList = listFiles();
    request->send(200, "text/plain", fileList);
  });
  
  server.on("/reset", HTTP_GET, [](AsyncWebServerRequest *request){
    request->send(200, "reset");
    ESP.restart();
  });

  server.on("/download", HTTP_GET, [](AsyncWebServerRequest *request) {
    if (request->hasParam("file")) {
      String fileName = request->getParam("file")->value();
      File file = SD.open("/" + fileName, FILE_READ);
      if (!file || file.isDirectory()) {
        if (file) file.close();
        request->send(404, "text/plain", "File not found");
        return;
      }

      AsyncWebServerResponse *response = request->beginChunkedResponse(
            "audio/wav",
            [file](uint8_t *buffer, size_t maxLen, size_t index) mutable -> size_t {
                size_t bytesRead = file.read(buffer, maxLen);

                if (bytesRead == 0) {
                    file.close();
                }

                return bytesRead;
            });

      response->addHeader("Content-Disposition", "attachment; filename=" + fileName);
      response->addHeader("Transfer-Encoding", "chunked");
      request->send(response);
    } else {
      request->send(400, "text/plain", "File parameter missing");
    }
  });

  server.on("/set_time", HTTP_GET, [](AsyncWebServerRequest *request){
    if (request->hasParam("time")) {
      String timeStr = request->getParam("time")->value();
      time_t now = timeStr.toInt();
      struct timeval tv = { .tv_sec = now };
      settimeofday(&tv, NULL);
      request->send(200, "text/plain", "Time set successfully");
    } else {
      request->send(400, "text/plain", "Time parameter missing");
    }
  });

  server.on("/delete", HTTP_GET, [](AsyncWebServerRequest *request){
    if (request->hasParam("file")) {
      String fileName = request->getParam("file")->value();
      deleteFile(("/" + fileName).c_str());
      request->send(200, "text/plain", "File deleted successfully");
    } else {
      request->send(400, "text/plain", "File parameter missing");
    }
  });

  server.on("/rename", HTTP_GET, [](AsyncWebServerRequest *request){
    if (request->hasParam("old") && request->hasParam("new")) {
      String oldName = request->getParam("old")->value();
      String newName = request->getParam("new")->value();
      if (renameFile(("/" + oldName).c_str(), ("/" + newName).c_str())) {
        request->send(200, "text/plain", "File renamed successfully");
      } else {
        request->send(500, "text/plain", "File rename failed");
      }
    } else {
      request->send(400, "text/plain", "File parameters missing");
    }
  });
  server.on("/update", HTTP_POST, [](AsyncWebServerRequest *request) {
    request->send(200, "text/plain", "Firmware update started");
}, [](AsyncWebServerRequest *request, const String& filename, size_t index, uint8_t *data, size_t len, bool final) {
    if (!index) {
        Serial.printf("Update Start: %s\n", filename.c_str());
        if (!Update.begin(UPDATE_SIZE_UNKNOWN)) { // Mulai update
            Update.printError(Serial);
        }
    }

    if (Update.write(data, len) != len) {
        Update.printError(Serial);
    }

    if (final) {
        if (Update.end(true)) {
            Serial.printf("Update Success: %u bytes\n", index + len);
        } else {
            Update.printError(Serial);
        }
    }
});

  server.begin();
}

void loop() {
  if (isRecording) {
    recordAudio();
    unsigned long currentMillis = millis();
    
    // Jika waktu sekarang sudah lebih dari interval blinking
    if (currentMillis - previousMillis >= blinkInterval) {
      previousMillis = currentMillis;
      ledState = !ledState;  // Toggle LED
      digitalWrite(LED_PIN, ledState ? HIGH : LOW);
    }
  } else {
    digitalWrite(LED_PIN, LOW);  // Matikan LED jika tidak merekam
  }
}

void startRecording() {
  if (isRecording) return;

  time_t now;
  time(&now);
  now += 7 * 3600; // Tambahkan offset waktu 7 jam untuk WIB (GMT+7)
  struct tm timeinfo;
  localtime_r(&now, &timeinfo);
  char fileName[40];
  snprintf(fileName, sizeof(fileName), "/%s_%02d%02d_%02d%02d.wav", Record_Name, timeinfo.tm_mon + 1, timeinfo.tm_mday, timeinfo.tm_hour, timeinfo.tm_min);

  recordingFile = SD.open(fileName, FILE_WRITE);

  if (!recordingFile) {
    Serial.println("Failed to open file for writing");
    return;
  }

  // Write WAV header
  writeWavHeader(recordingFile, 0);
  WiFi.setSleep(true);
  isRecording = true;
  totalSamples = 0;

  Serial.println("Recording started");
}

void stopRecording() {
  if (!isRecording) return;

  isRecording = false;
  recordingFile.seek(0);
  writeWavHeader(recordingFile, totalSamples * (bitDepth / 8));
  recordingFile.close();

  digitalWrite(LED_PIN, LOW);

  Serial.println("Recording stopped");
}
/*
//non gain, only 16 bit bcs 32 bit -> 24 bit frame only, skip 1 bit and parsing 16 bit depth
void recordAudio() {
  uint8_t i2sData[1024];  // Buffer untuk data mentah dari I2S
  size_t bytesRead = 0;

  i2s_read(I2S_PORT, &i2sData, sizeof(i2sData), &bytesRead, portMAX_DELAY);

  if (bytesRead > 0) {
    size_t numSamples = bytesRead / 4;  // Karena 1 sample = 4 byte dalam mode 32-bit
    int16_t processedSamples[numSamples];  // Buffer untuk data 16-bit yang akan disimpan
    
    for (size_t i = 0; i < numSamples; ++i) {
      size_t byteIndex = i * 4;  // 4 byte per sample
      int32_t value = ((int32_t*)(i2sData + byteIndex))[0] >> 8;  // Ambil 16-bit paling signifikan dengan delay 1 bit
      processedSamples[i] = (int16_t)value;
    }

    recordingFile.write((uint8_t*)processedSamples, numSamples * sizeof(int16_t));
    totalSamples += numSamples;
  }
}
*/


void recordAudio() {
  uint8_t i2sData[1024];
  size_t bytesRead = 0;
  float gain = 18.0f;  // Atur gainnya disini. normal bagus 18, tinggi bisa clipping <50

  i2s_read(I2S_PORT, &i2sData, sizeof(i2sData), &bytesRead, portMAX_DELAY);
  if (bytesRead > 0) {
    // Asumsi bit depth adalah 16-bit
    int16_t* samples = (int16_t*)i2sData;
    size_t numSamples = bytesRead / sizeof(int16_t);

    // Amplify and find max sample value for normalization
    int32_t maxSample = 0;
    for (size_t i = 0; i < numSamples; ++i) {
      int32_t sample = samples[i] * gain;

      // Hindari clipping
      if (sample > INT16_MAX) {
        sample = INT16_MAX;
      } else if (sample < INT16_MIN) {
        sample = INT16_MIN;
      }

      samples[i] = (int16_t)sample;
      if (abs(sample) > maxSample) {
        maxSample = abs(sample);
      }
    }

    // Normalize if maxSample is greater than 0
    if (maxSample > 0) {
      float normalizationFactor = (float)INT16_MAX / maxSample;
      for (size_t i = 0; i < numSamples; ++i) {
        samples[i] = (int16_t)(samples[i] * normalizationFactor);
      }
    }

    recordingFile.write(i2sData, bytesRead);
    totalSamples += bytesRead / (bitDepth / 8);
  }
}

void writeWavHeader(File file, int fileSize) {
  byte header[44];
  int sampleRate = 48000;
  int bitsPerSample = 32; //uncoment yang non gain, ganti ini ke 16bit karena di skip 8 bit
  int channels = 1;

  int byteRate = sampleRate * channels * bitsPerSample / 8;
  int blockAlign = channels * bitsPerSample / 8;

  // RIFF header
  header[0] = 'R'; header[1] = 'I'; header[2] = 'F'; header[3] = 'F';
  header[4] = (byte)(fileSize & 0xff);
  header[5] = (byte)((fileSize >> 8) & 0xff);
  header[6] = (byte)((fileSize >> 16) & 0xff);
  header[7] = (byte)((fileSize >> 24) & 0xff);
  header[8] = 'W'; header[9] = 'A'; header[10] = 'V'; header[11] = 'E';

  // fmt subchunk
  header[12] = 'f'; header[13] = 'm'; header[14] = 't'; header[15] = ' ';
  header[16] = 16; header[17] = 0; header[18] = 0; header[19] = 0;
  header[20] = 1; header[21] = 0;
  header[22] = channels; header[23] = 0;
  header[24] = (byte)(sampleRate & 0xff);
  header[25] = (byte)((sampleRate >> 8) & 0xff);
  header[26] = (byte)((sampleRate >> 16) & 0xff);
  header[27] = (byte)((sampleRate >> 24) & 0xff);
  header[28] = (byte)(byteRate & 0xff);
  header[29] = (byte)((byteRate >> 8) & 0xff);
  header[30] = (byte)((byteRate >> 16) & 0xff);
  header[31] = (byte)((byteRate >> 24) & 0xff);
  header[32] = blockAlign; header[33] = 0;
  header[34] = bitsPerSample; header[35] = 0;

  // data subchunk
  header[36] = 'd'; header[37] = 'a'; header[38] = 't'; header[39] = 'a';
  header[40] = (byte)((fileSize - 44) & 0xff);
  header[41] = (byte)(((fileSize - 44) >> 8) & 0xff);
  header[42] = (byte)(((fileSize - 44) >> 16) & 0xff);
  header[43] = (byte)(((fileSize - 44) >> 24) & 0xff);

  file.write(header, 44);
}

String listFiles() {
  String fileList = "";
  File root = SD.open("/");
  File file = root.openNextFile();
  while (file) {
    float fileSizeMB = file.size() / (1024.0 * 1024.0); // Calculate file size in MB
    fileList += String(file.name()) + " - " + String(fileSizeMB, 2) + " MB\n";
    file = root.openNextFile();
  }
  return fileList;
}

void deleteFile(const char* path) {
  if (SD.remove(path)) {
    Serial.println("File deleted successfully");
  } else {
    Serial.println("Failed to delete file");
  }
}

bool renameFile(const char* oldName, const char* newName) {
  if (SD.rename(oldName, newName)) {
    Serial.println("File renamed successfully");
    return true;
  } else {
    Serial.println("Failed to rename file");
    return false;
  }
}

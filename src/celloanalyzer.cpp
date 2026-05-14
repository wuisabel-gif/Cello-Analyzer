#include "Particle.h"
#include <Wire.h>
#define BLYNK_TEMPLATE_ID "TMPL_CELLO_ANALYZER"
#define BLYNK_TEMPLATE_NAME "cello analyzer"
#define BLYNK_AUTH_TOKEN "KQiO_lM4WwpVXSjoO49fXFKuHVoepqm5"
#include <BlynkSimpleParticle.h>
#include "SparkFunMicroOLED.h"
#include "DHT20.h"
#include "Microphone_PDM.h"

SYSTEM_MODE(AUTOMATIC);
SYSTEM_THREAD(ENABLED);
SerialLogHandler logHandler(LOG_LEVEL_WARN);

namespace {

// ===== Variables and Libraries =====

const pin_t MIC_CLK_PIN = A0;
const pin_t MIC_DATA_PIN = A1;
const pin_t RGB_RED_PIN = D2;
const pin_t RGB_GREEN_PIN = D3;
const pin_t RGB_BLUE_PIN = D4;
const pin_t BUZZER_PIN = A5;
const pin_t SWITCH_PIN = D6;
const pin_t BUTTON_PIN = D7;

const int WAVEFORM_POINT_COUNT = 64;
const int HISTORY_POINT_COUNT = 48;
const int NOISE_FLOOR = 24;
const int BAND_HYSTERESIS_PERCENT = 8;
const int PDM_SAMPLE_RATE = 16000;

const unsigned long UI_UPDATE_MS = 2500;
const unsigned long BUTTON_DEBOUNCE_MS = 200;
const unsigned long ENVIRONMENT_READ_MS = 2500;
const unsigned long DHT20_MIN_READ_GAP_MS = 1200;
const unsigned long PERFORMANCE_PUBLISH_MS = 1000;
const unsigned long ENVIRONMENT_PUBLISH_MS = 2500;
const unsigned long RAW_SERIAL_PRINT_MS = 1000;
const unsigned long DYNAMIC_MAX_DECAY_MS = 8000;
const unsigned long BLYNK_UPDATE_MS = 2500;

const double SAFE_TEMP_MIN_C = 15.0;
const double SAFE_TEMP_MAX_C = 30.0;
const double SAFE_HUMIDITY_MIN = 40.0;
const double SAFE_HUMIDITY_MAX = 60.0;

#define PIN_RESET 9
#define DC_JUMPER 1

enum DeviceMode {
    MODE_PERFORMANCE,
    MODE_TREND,
    MODE_ENVIRONMENT,
    MODE_ENVIRONMENT_HISTORY
};

enum LedColor {
    LED_OFF,
    LED_BLUE,
    LED_CYAN,
    LED_GREEN,
    LED_YELLOW,
    LED_WHITE,
    LED_RED
};

MicroOLED oled(MODE_I2C, PIN_RESET, DC_JUMPER);
DHT20 dht20;

unsigned long lastUiUpdateMs = 0;
unsigned long lastButtonPressMs = 0;
unsigned long lastEnvironmentReadMs = 0;
unsigned long lastPerformancePublishMs = 0;
unsigned long lastEnvironmentPublishMs = 0;
unsigned long lastDisabledSerialMs = 0;
unsigned long lastRawSerialPrintMs = 0;
unsigned long lastDynamicMaxAdjustMs = 0;
unsigned long lastBlynkUpdateMs = 0;

int smoothedAmplitude = 0;
int currentVolumePercent = 0;
int dynamicMax = 2000;

int lastMicSample = 0;
int lastMicMin = 0;
int lastMicMax = 0;
int lastMicAverage = 0;
int lastMicPeakDeviation = 0;
int lastMicCenteredAmplitude = 0;

int waveformSamples[WAVEFORM_POINT_COUNT] = {0};
int volumeHistory[HISTORY_POINT_COUNT] = {0};

int currentPerformanceBand = 0;
int lastPerformanceBandChange = 0;
String pendingDynamicTone = "";

double currentTemperatureC = NAN;
double currentHumidity = NAN;
double maxTemperatureC = -1000.0;
double minTemperatureC = 1000.0;
double maxHumidity = -1000.0;
double minHumidity = 1000.0;

bool dhtConnected = false;
bool hasEnvironmentReading = false;
bool performanceDisplayDirty = true;
bool microphoneReady = false;
int microphoneInitError = SYSTEM_ERROR_NONE;

String pendingPerformanceLed = "pp";
String pendingEnvironmentLed = "OK";

DeviceMode currentMode = MODE_PERFORMANCE;
bool systemEnabled = true;
int previousButtonState = HIGH;

String currentDynamicLabel = "pp";
String currentModeLabel = "performance";
String currentEnvironmentAlert = "OK";
String currentCelloHealthMessage = "Sensor err";

int historyWriteIndex = 0;
int historySampleCount = 0;

const char* getDynamicLevel(int volumePercent);
int getPerformanceBand(int volumePercent);
int getStablePerformanceBand(int volumePercent, int currentBand);
void buzzDynamicShift(const String& previousDynamic, const String& newDynamic);
void updatePerformanceLed(const String& dynamicLevel);
void recordVolumeHistory();
int getDynamicHistoryPercent(const char* dynamicLabel);
void setColor(LedColor c);
void updateOLED();
void updateNextState(unsigned long curMillis);
void publishInitialStateData();
void advanceToNextMode();
void updateBlynkDashboard();
bool isSoftDynamicGroup(const String& dynamicLabel);

// ===== Microphone and Volume Processing =====

void decayDynamicMaxIfNeeded() {
    if (millis() - lastDynamicMaxAdjustMs < DYNAMIC_MAX_DECAY_MS) {
        return;
    }
    lastDynamicMaxAdjustMs = millis();

    if (dynamicMax > 2500) {
        dynamicMax -= 150;
    } else if (dynamicMax > 1800) {
        dynamicMax -= 75;
    }

    if (dynamicMax < 1200) {
        dynamicMax = 1200;
    }
}

void processMicrophoneSamples(const int16_t* samples, size_t numSamples) {
    if (samples == nullptr || numSamples == 0) {
        return;
    }

    int minVal = samples[0];
    int maxVal = samples[0];
    int sampleTotal = 0;

    for (size_t i = 0; i < numSamples; i++) {
        int sample = samples[i];
        lastMicSample = sample;
        sampleTotal += sample;

        if (sample < minVal) {
            minVal = sample;
        }
        if (sample > maxVal) {
            maxVal = sample;
        }

        size_t waveformIndex = (i * WAVEFORM_POINT_COUNT) / numSamples;
        if (waveformIndex >= WAVEFORM_POINT_COUNT) {
            waveformIndex = WAVEFORM_POINT_COUNT - 1;
        }
        waveformSamples[waveformIndex] = sample;
    }

    int averageSample = sampleTotal / static_cast<int>(numSamples);

    int centeredMagnitudeTotal = 0;
    for (size_t i = 0; i < numSamples; i++) {
        centeredMagnitudeTotal += abs(samples[i] - averageSample);
    }

    int amplitude = centeredMagnitudeTotal / static_cast<int>(numSamples);
    int peakDeviation = max(abs(maxVal - averageSample), abs(minVal - averageSample));

    if (amplitude < NOISE_FLOOR) {
        amplitude = 0;
    }
    if (peakDeviation < (NOISE_FLOOR / 2)) {
        peakDeviation = 0;
    }

    lastMicMin = minVal;
    lastMicMax = maxVal;
    lastMicAverage = averageSample;
    lastMicPeakDeviation = peakDeviation;
    lastMicCenteredAmplitude = amplitude;

    int combinedAmplitude = (amplitude + peakDeviation) / 2;
    smoothedAmplitude = ((smoothedAmplitude * 3) + combinedAmplitude) / 4;

    if (smoothedAmplitude > dynamicMax) {
        dynamicMax = smoothedAmplitude;
    }
    decayDynamicMaxIfNeeded();

    currentVolumePercent = (smoothedAmplitude * 100) / max(dynamicMax, 1);
    if (currentVolumePercent < 0) currentVolumePercent = 0;
    if (currentVolumePercent > 100) currentVolumePercent = 100;

    int newPerformanceBand = getStablePerformanceBand(currentVolumePercent, currentPerformanceBand);
    String newDynamicLabel = getDynamicLevel(currentVolumePercent);

    if (newPerformanceBand != currentPerformanceBand) {
        lastPerformanceBandChange = (newPerformanceBand > currentPerformanceBand) ? 1 : -1;
        if (isSoftDynamicGroup(currentDynamicLabel) != isSoftDynamicGroup(newDynamicLabel)) {
            buzzDynamicShift(currentDynamicLabel, newDynamicLabel);
        }
        currentPerformanceBand = newPerformanceBand;
        currentDynamicLabel = newDynamicLabel;
        performanceDisplayDirty = true;
    } else if (newDynamicLabel != currentDynamicLabel) {
        currentDynamicLabel = newDynamicLabel;
        performanceDisplayDirty = true;
    }

    pendingPerformanceLed = currentDynamicLabel;
}

const char* getDynamicLevel(int volumePercent) {
    if (volumePercent < 10) return "pp";
    if (volumePercent < 20) return "p";
    if (volumePercent < 40) return "mp";
    if (volumePercent < 65) return "mf";
    if (volumePercent < 85) return "f";
    return "ff";
}

int getPerformanceBand(int volumePercent) {
    if (volumePercent < 25) return 0;
    if (volumePercent < 50) return 1;
    if (volumePercent < 75) return 2;
    return 3;
}

int getStablePerformanceBand(int volumePercent, int currentBand) {
    if (currentBand <= 0) {
        if (volumePercent >= 25 + BAND_HYSTERESIS_PERCENT) return 1;
        return 0;
    }
    if (currentBand == 1) {
        if (volumePercent < 25 - BAND_HYSTERESIS_PERCENT) return 0;
        if (volumePercent >= 50 + BAND_HYSTERESIS_PERCENT) return 2;
        return 1;
    }
    if (currentBand == 2) {
        if (volumePercent < 50 - BAND_HYSTERESIS_PERCENT) return 1;
        if (volumePercent >= 75 + BAND_HYSTERESIS_PERCENT) return 3;
        return 2;
    }
    if (volumePercent < 75 - BAND_HYSTERESIS_PERCENT) return 2;
    return 3;
}

int getDynamicToneFrequency(const String& dynamicLevel) {
    if (dynamicLevel == "pp") return 523;
    if (dynamicLevel == "p") return 587;
    if (dynamicLevel == "mp") return 659;
    if (dynamicLevel == "mf") return 698;
    if (dynamicLevel == "f") return 784;
    return 880;
}

void buzzDynamicShift(const String& previousDynamic, const String& newDynamic) {
    if (!systemEnabled || previousDynamic == newDynamic) return;
    pendingDynamicTone = newDynamic;
}

bool isSoftDynamicGroup(const String& dynamicLabel) {
    return dynamicLabel == "pp" || dynamicLabel == "p" || dynamicLabel == "mp";
}

void setRgbColor(bool redOn, bool greenOn, bool blueOn) {
    digitalWrite(RGB_RED_PIN, redOn ? HIGH : LOW);
    digitalWrite(RGB_GREEN_PIN, greenOn ? HIGH : LOW);
    digitalWrite(RGB_BLUE_PIN, blueOn ? HIGH : LOW);
}

void setColor(LedColor c) {
    switch (c) {
        case LED_BLUE:
            setRgbColor(false, false, true);
            break;
        case LED_CYAN:
            setRgbColor(false, true, true);
            break;
        case LED_GREEN:
            setRgbColor(false, true, false);
            break;
        case LED_YELLOW:
            setRgbColor(true, true, false);
            break;
        case LED_WHITE:
            setRgbColor(true, true, true);
            break;
        case LED_RED:
            setRgbColor(true, false, false);
            break;
        case LED_OFF:
        default:
            setRgbColor(false, false, false);
            break;
    }
}

void updatePerformanceLed(const String& dynamicLevel) {
    if (dynamicLevel == "pp") {
        setColor(LED_BLUE);
    } else if (dynamicLevel == "p") {
        setColor(LED_CYAN);
    } else if (dynamicLevel == "mp") {
        setColor(LED_GREEN);
    } else if (dynamicLevel == "mf") {
        setColor(LED_YELLOW);
    } else if (dynamicLevel == "f") {
        setColor(LED_WHITE);
    } else {
        setColor(LED_RED);
    }
}

// ===== RGB LED and Buzzer Feedback =====

void updateEnvironmentLed(const String& alertState) {
    if (alertState == "OK") {
        setColor(LED_GREEN);
    } else if (alertState == "WARN") {
        setColor(LED_YELLOW);
    } else {
        setColor(LED_RED);
    }
}

// ===== OLED Functions =====

void clearDisplay() {
    oled.clear(PAGE);
}

void drawDisabledScreen() {
    clearDisplay();
    oled.setFontType(1);
    oled.setCursor(0, 0);
    oled.print("System Off");
    oled.setFontType(0);
    oled.setCursor(0, 20);
    oled.print("Flip D6");
    oled.setCursor(0, 32);
    oled.print("switch on");
    oled.display();
}

void drawPerformanceScreen() {
    clearDisplay();

    int signalRange = lastMicMax - lastMicMin;
    if (signalRange < 1) signalRange = 1;

    for (int x = 0; x < WAVEFORM_POINT_COUNT - 1; x++) {
        int y0 = 2 + ((waveformSamples[x] - lastMicMin) * 27) / signalRange;
        int y1 = 2 + ((waveformSamples[x + 1] - lastMicMin) * 27) / signalRange;
        y0 = 29 - y0;
        y1 = 29 - y1;
        oled.line(x, y0, x + 1, y1);
    }

    oled.setFontType(0);
    oled.setCursor(0, 34);
    oled.print(currentDynamicLabel);
    oled.setCursor(24, 34);
    oled.print(currentVolumePercent);
    oled.print("%");
    oled.display();
}

void drawTrendScreen() {
    clearDisplay();
    oled.setFontType(0);
    oled.setCursor(0, 0);
    oled.print("Dyn Trend");

    oled.setCursor(0, 12);
    oled.print("pp");
    oled.print(getDynamicHistoryPercent("pp"));
    oled.print("%");
    oled.setCursor(32, 12);
    oled.print("p");
    oled.print(getDynamicHistoryPercent("p"));
    oled.print("%");

    oled.setCursor(0, 24);
    oled.print("mp");
    oled.print(getDynamicHistoryPercent("mp"));
    oled.print("%");
    oled.setCursor(32, 24);
    oled.print("mf");
    oled.print(getDynamicHistoryPercent("mf"));
    oled.print("%");

    oled.setCursor(0, 36);
    oled.print("f");
    oled.print(getDynamicHistoryPercent("f"));
    oled.print("%");
    oled.setCursor(32, 36);
    oled.print("ff");
    oled.print(getDynamicHistoryPercent("ff"));
    oled.print("%");
    oled.display();
}

void drawEnvironmentScreen() {
    clearDisplay();
    oled.setFontType(0);
    oled.setCursor(0, 0);
    oled.print("Temp:");

    if (hasEnvironmentReading && !isnan(currentTemperatureC) && !isnan(currentHumidity)) {
        oled.setCursor(0, 10);
        oled.print(String(currentTemperatureC, 1));
        oled.print(" C");
        oled.setCursor(0, 26);
        oled.print("Hum:");
        oled.setCursor(0, 36);
        oled.print(String(currentHumidity, 1));
        oled.print("%");
    } else {
        oled.setCursor(0, 10);
        oled.print("--.- C");
        oled.setCursor(0, 26);
        oled.print("Hum:");
        oled.setCursor(0, 36);
        oled.print("--.-%");
    }

    oled.display();
}

void drawEnvironmentHistoryScreen() {
    clearDisplay();
    oled.setFontType(0);
    oled.setCursor(0, 0);
    oled.print("Temp");

    if (hasEnvironmentReading) {
        oled.setCursor(0, 8);
        oled.print("H:");
        oled.print(String(maxTemperatureC, 1));
        oled.print("C");
        oled.setCursor(0, 16);
        oled.print("L:");
        oled.print(String(minTemperatureC, 1));
        oled.print("C");
        oled.setCursor(0, 26);
        oled.print("Hum");
        oled.setCursor(0, 34);
        oled.print("H:");
        oled.print(String(maxHumidity, 0));
        oled.print("%");
        oled.setCursor(0, 42);
        oled.print("L:");
        oled.print(String(minHumidity, 0));
        oled.print("%");
    } else {
        oled.setCursor(0, 12);
        oled.print("No env");
        oled.setCursor(0, 24);
        oled.print("history");
    }

    oled.display();
}

void updateOLED() {
    if (!systemEnabled) {
        drawDisabledScreen();
        return;
    }

    if (currentMode == MODE_PERFORMANCE) {
        drawPerformanceScreen();
    } else if (currentMode == MODE_TREND) {
        drawTrendScreen();
    } else if (currentMode == MODE_ENVIRONMENT) {
        drawEnvironmentScreen();
    } else {
        drawEnvironmentHistoryScreen();
    }
}

void publishInitialStateData() {
    if (!Particle.connected()) return;

    String payload;
    payload.reserve(512);
    payload += "[";
    payload += String::format("{\"key\":\"volume\",\"value\":%d},", currentVolumePercent);
    payload += String::format("{\"key\":\"temperature\",\"value\":%.1f},", currentTemperatureC);
    payload += String::format("{\"key\":\"humidity\",\"value\":%.1f},", currentHumidity);
    payload += String::format("{\"key\":\"dynamic\",\"value\":\"%s\"}", currentDynamicLabel.c_str());
    payload += "]";

    Particle.publish("Cello_Analyzer", payload, PRIVATE);
}

String classifyEnvironmentAlert() {
    if (!hasEnvironmentReading || isnan(currentTemperatureC) || isnan(currentHumidity)) {
        return "ERROR";
    }

    bool tempOutOfRange = currentTemperatureC < SAFE_TEMP_MIN_C || currentTemperatureC > SAFE_TEMP_MAX_C;
    bool humidityOutOfRange = currentHumidity < SAFE_HUMIDITY_MIN || currentHumidity > SAFE_HUMIDITY_MAX;

    if (tempOutOfRange && humidityOutOfRange) return "ALERT";
    if (tempOutOfRange || humidityOutOfRange) return "WARN";
    return "OK";
}

String getCelloHealthMessage() {
    if (!hasEnvironmentReading || isnan(currentTemperatureC) || isnan(currentHumidity)) return "Sensor err";
    if (currentHumidity < SAFE_HUMIDITY_MIN) return "Dry air";
    if (currentHumidity > SAFE_HUMIDITY_MAX) return "Humid air";
    if (currentTemperatureC < SAFE_TEMP_MIN_C) return "Too cold";
    if (currentTemperatureC > SAFE_TEMP_MAX_C) return "Too warm";
    return "Cello safe";
}

// ===== Environment Sensing =====

void updateEnvironmentReading() {
    if (lastEnvironmentReadMs != 0 && millis() - lastEnvironmentReadMs < DHT20_MIN_READ_GAP_MS) return;

    lastEnvironmentReadMs = millis();

    int status = DHT20_ERROR_CONNECT;
    int attempts = hasEnvironmentReading ? 1 : 3;

    for (int attempt = 0; attempt < attempts; attempt++) {
        status = dht20.read();
        if (status == 0) break;
        delay(60);
    }

    if (status == 0) {
        dhtConnected = true;
        hasEnvironmentReading = true;
        currentTemperatureC = dht20.getTemperature();
        currentHumidity = dht20.getHumidity();

        if (currentTemperatureC > maxTemperatureC) maxTemperatureC = currentTemperatureC;
        if (currentTemperatureC < minTemperatureC) minTemperatureC = currentTemperatureC;
        if (currentHumidity > maxHumidity) maxHumidity = currentHumidity;
        if (currentHumidity < minHumidity) minHumidity = currentHumidity;

        currentEnvironmentAlert = classifyEnvironmentAlert();
        currentCelloHealthMessage = getCelloHealthMessage();
        pendingEnvironmentLed = currentEnvironmentAlert;
    } else {
        dhtConnected = false;
        if (!hasEnvironmentReading) {
            currentTemperatureC = NAN;
            currentHumidity = NAN;
            currentEnvironmentAlert = "ERROR";
            currentCelloHealthMessage = "Sensor err";
        }
        pendingEnvironmentLed = currentEnvironmentAlert;
        Log.warn("DHT20 read failed: %d", status);
    }
}

void samplePerformance() {
    if (!microphoneReady) return;

    Microphone_PDM::instance().noCopySamples([](void* pSamples, size_t numSamples) {
        processMicrophoneSamples(static_cast<const int16_t*>(pSamples), numSamples);
    });
}

void readEnvironmentIfDue() {
    if (millis() - lastEnvironmentReadMs < ENVIRONMENT_READ_MS) return;
    updateEnvironmentReading();
}

void recordVolumeHistory() {
    volumeHistory[historyWriteIndex] = currentVolumePercent;
    historyWriteIndex = (historyWriteIndex + 1) % HISTORY_POINT_COUNT;
    if (historySampleCount < HISTORY_POINT_COUNT) {
        historySampleCount++;
    }
}

int getDynamicHistoryPercent(const char* dynamicLabel) {
    if (historySampleCount == 0) return 0;

    int matches = 0;
    for (int i = 0; i < historySampleCount; i++) {
        int index = (historyWriteIndex - historySampleCount + i + HISTORY_POINT_COUNT) % HISTORY_POINT_COUNT;
        if (String(getDynamicLevel(volumeHistory[index])) == dynamicLabel) {
            matches++;
        }
    }

    return (matches * 100) / historySampleCount;
}

// ===== User Input and Mode Changes =====

void updateSwitchState() {
    bool requestedEnabled = digitalRead(SWITCH_PIN) == HIGH;
    if (requestedEnabled == systemEnabled) return;

    systemEnabled = requestedEnabled;
    if (!systemEnabled) setColor(LED_OFF);
    updateOLED();
}

void advanceToNextMode() {
    switch (currentMode) {
        case MODE_PERFORMANCE:
            currentMode = MODE_TREND;
            currentModeLabel = "trend";
            break;
        case MODE_TREND:
            currentMode = MODE_ENVIRONMENT;
            currentModeLabel = "environment";
            updateEnvironmentReading();
            break;
        case MODE_ENVIRONMENT:
            currentMode = MODE_ENVIRONMENT_HISTORY;
            currentModeLabel = "environmentHistory";
            break;
        case MODE_ENVIRONMENT_HISTORY:
        default:
            currentMode = MODE_PERFORMANCE;
            currentModeLabel = "performance";
            performanceDisplayDirty = true;
            break;
    }
}

void updateNextState(unsigned long curMillis) {
    updateSwitchState();

    int buttonState = digitalRead(BUTTON_PIN);
    bool pressed = (previousButtonState == HIGH && buttonState == LOW);
    previousButtonState = buttonState;

    if (!systemEnabled || !pressed) return;
    if (curMillis - lastButtonPressMs < BUTTON_DEBOUNCE_MS) return;

    lastButtonPressMs = curMillis;
    advanceToNextMode();
    updateOLED();
}

void updateBlynkDashboard() {
    Blynk.virtualWrite(V1, currentModeLabel);
    Blynk.virtualWrite(V2, currentDynamicLabel);
    Blynk.virtualWrite(V3, currentVolumePercent);
    Blynk.virtualWrite(V4, String(currentTemperatureC, 1));
    Blynk.virtualWrite(V5, String(currentHumidity, 1));
    Blynk.virtualWrite(V6, currentCelloHealthMessage);
    Blynk.virtualWrite(V7, currentEnvironmentAlert);
    Blynk.virtualWrite(V8, String::format("pp %d%% p %d%% mp %d%% mf %d%% f %d%% ff %d%%",
        getDynamicHistoryPercent("pp"),
        getDynamicHistoryPercent("p"),
        getDynamicHistoryPercent("mp"),
        getDynamicHistoryPercent("mf"),
        getDynamicHistoryPercent("f"),
        getDynamicHistoryPercent("ff")));
    Blynk.virtualWrite(V9, String::format("T H %.1f  T L %.1f", maxTemperatureC, minTemperatureC));
    Blynk.virtualWrite(V10, String::format("H H %.0f  H L %.0f", maxHumidity, minHumidity));
}

int cloudSetMode(String command) {
    command.toLowerCase();

    if (command == "performance") {
        currentMode = MODE_PERFORMANCE;
        currentModeLabel = "Current Performance";
        performanceDisplayDirty = true;
    } else if (command == "trend") {
        currentMode = MODE_TREND;
        currentModeLabel = "Performance Summary";
    } else if (command == "environment") {
        currentMode = MODE_ENVIRONMENT;
        currentModeLabel = "Current Environment";
        updateEnvironmentReading();
    } else if (command == "environmenthistory") {
        currentMode = MODE_ENVIRONMENT_HISTORY;
        currentModeLabel = "Environment Summary";
    } else if (command == "off") {
        systemEnabled = false;
        setColor(LED_OFF);
    } else if (command == "on") {
        systemEnabled = true;
    } else {
        return -1;
    }

    updateOLED();
    return 1;
}

} 

// ===== Setup =====

void setup() {
    Serial.begin(9600);
    waitFor(Serial.isConnected, 3000);
    Serial.println("Cello analyzer starting");

    pinMode(RGB_RED_PIN, OUTPUT);
    pinMode(RGB_GREEN_PIN, OUTPUT);
    pinMode(RGB_BLUE_PIN, OUTPUT);
    pinMode(BUZZER_PIN, OUTPUT);
    pinMode(SWITCH_PIN, INPUT_PULLUP);
    pinMode(BUTTON_PIN, INPUT_PULLUP);

    Wire.begin();
    oled.begin();
    oled.clear(ALL);
    oled.display();
    delay(1000);

    microphoneInitError = Microphone_PDM::instance()
        .withOutputSize(Microphone_PDM::OutputSize::SIGNED_16)
        .withRange(Microphone_PDM::Range::RANGE_2048)
        .withSampleRate(PDM_SAMPLE_RATE)
        .init();

    if (microphoneInitError == SYSTEM_ERROR_NONE) {
        Microphone_PDM::instance().start();
        microphoneReady = true;
    } else {
        Log.warn("PDM microphone init failed: %d", microphoneInitError);
    }

    dhtConnected = dht20.begin();
    currentEnvironmentAlert = dhtConnected ? "OK" : "ERROR";
    currentCelloHealthMessage = dhtConnected ? "Waiting..." : "Sensor err";
    systemEnabled = digitalRead(SWITCH_PIN) == HIGH;

    if (dhtConnected) {
        delay(100);
        updateEnvironmentReading();
    }

    Blynk.begin(BLYNK_AUTH_TOKEN);

    Particle.function("setMode", cloudSetMode);
    Particle.variable("mode", currentModeLabel);
    Particle.variable("dynamic", currentDynamicLabel);
    Particle.variable("volume", currentVolumePercent);
    Particle.variable("raw", smoothedAmplitude);
    Particle.variable("temp", currentTemperatureC);
    Particle.variable("hum", currentHumidity);
    Particle.variable("alert", currentEnvironmentAlert);
    Particle.variable("celloHealth", currentCelloHealthMessage);

    updateOLED();

    Serial.printlnf(
        "Startup | mode=%s | micReady=%d | dhtConnected=%d | systemEnabled=%d",
        currentModeLabel.c_str(),
        microphoneReady ? 1 : 0,
        dhtConnected ? 1 : 0,
        systemEnabled ? 1 : 0
    );

    Log.warn("Cello Dynamics Analyst started");
}

// ===== Main Loop =====

void loop() {
    unsigned long curMillis = millis();
    Blynk.run();
    updateNextState(curMillis);

    if (!systemEnabled) {
        if (curMillis - lastDisabledSerialMs >= UI_UPDATE_MS) {
            lastDisabledSerialMs = curMillis;
            Serial.println("System off");
        }
        delay(25);
        return;
    }

    bool dueUiUpdate = curMillis - lastUiUpdateMs >= UI_UPDATE_MS;
    if (dueUiUpdate) {
        lastUiUpdateMs = curMillis;
        recordVolumeHistory();
    }

    samplePerformance();

    if (curMillis - lastRawSerialPrintMs >= RAW_SERIAL_PRINT_MS) {
        lastRawSerialPrintMs = curMillis;
        Serial.printlnf(
            "Amp:%d | Peak:%d | Vol:%d%% | Dyn:%s | MaxRef:%d",
            smoothedAmplitude,
            lastMicPeakDeviation,
            currentVolumePercent,
            currentDynamicLabel.c_str(),
            dynamicMax
        );
    }

    readEnvironmentIfDue();

    if (currentMode == MODE_PERFORMANCE || currentMode == MODE_TREND) {
        updatePerformanceLed(pendingPerformanceLed);
    } else {
        updateEnvironmentLed(pendingEnvironmentLed);
    }

    if (curMillis - lastEnvironmentPublishMs >= ENVIRONMENT_PUBLISH_MS) {
        lastEnvironmentPublishMs = curMillis;
        publishInitialStateData();
    }

    if (dueUiUpdate) {
        updateOLED();
        performanceDisplayDirty = false;

        if (pendingDynamicTone.length() > 0) {
            tone(BUZZER_PIN, getDynamicToneFrequency(pendingDynamicTone), 90);
            pendingDynamicTone = "";
        }
    }

    if (curMillis - lastBlynkUpdateMs >= BLYNK_UPDATE_MS) {
        lastBlynkUpdateMs = curMillis;
        updateBlynkDashboard();
    }
}

// ===== Cloud and Mobile Output =====

void handleBlynkNextPageButton() {
    unsigned long curMillis = millis();
    if (!systemEnabled) {
        Serial.println("Blynk V0 ignored: system off");
        Blynk.virtualWrite(V0, 0);
        return;
    }
    if (curMillis - lastButtonPressMs < BUTTON_DEBOUNCE_MS) {
        Blynk.virtualWrite(V0, 0);
        return;
    }

    lastButtonPressMs = curMillis;
    advanceToNextMode();
    updateOLED();
    updateBlynkDashboard();
    Serial.printlnf("Blynk V0 page change -> %s", currentModeLabel.c_str());
    Blynk.virtualWrite(V0, 0);
}

BLYNK_WRITE(V0) {
    if (param.asInt() == 1) {
        handleBlynkNextPageButton();
    }
}



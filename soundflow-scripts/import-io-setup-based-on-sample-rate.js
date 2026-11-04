sf.ui.proTools.appActivate();

// Open Session Setup
sf.ui.proTools.menuClick({
    menuPath: ["Setup", "Session..."],
});

// Retrieve sample rate from UI (adjust selector as needed)
let sampleRateElement = sf.ui.proTools.window({ title: "Session Setup" }).element({ type: "StaticText", name: "Sample Rate" });

if (!sampleRateElement.exists) {
    throw new Error("Unable to retrieve sample rate from UI.");
}

const sessionSampleRate = sampleRateElement.value; // This might need adjustment based on actual UI structure

// Define file paths
const filePaths = {
    "44100": "/Users/edwardsokolowski/Documents/PT Prefs/2025-04-08 Backup 0002/Pro Tools/IO Settings/EAS DEFAULT 2025 44kHz.pio",
    "48000": "/Users/edwardsokolowski/Documents/PT Prefs/2025-04-11 Backup 0001/Pro Tools/IO Settings/EAS DEFAULT 2025 48kHz.pio"
};

// Validate sample rate
const ioFilePath = filePaths[sessionSampleRate.toString()];

if (!ioFilePath) {
    throw new Error(`Unsupported sample rate: ${sessionSampleRate}`);
}

// Open I/O Setup and import settings
sf.ui.proTools.menuClick({
    menuPath: ["Setup", "I/O..."],
});

sf.ui.proTools.window({ title: "I/O Setup" }).element({ type: "Button", name: "Import Settings..." }).click();

sf.keyboard.type({ text: ioFilePath });
sf.keyboard.press({ keys: "RETURN" });

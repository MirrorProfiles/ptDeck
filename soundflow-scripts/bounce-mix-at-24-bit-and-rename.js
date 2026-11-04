// Step 1: Activate the Pro Tools main window
sf.ui.proTools.appActivateMainWindow();

// Step 2: Get Sample Rate and Session Name (omit Bit Depth)
let sampleRate = sf.app.proTools.getSessionSampleRate().sampleRate;
const sessionName = sf.app.proTools.getSessionName().sessionName;

// Remove "SR" prefix from sample rate if present
if (sampleRate.startsWith("SR")) {
    sampleRate = sampleRate.slice(2);
}

// Convert sample rate to shorter form for the file name and set menu path for Bounce Mix
let shortSampleRate = '';
let menuSampleRate = '';
switch (sampleRate) {
    case '44100': 
        shortSampleRate = '44';
        menuSampleRate = '44.1 kHz';
        break;
    case '48000': 
        shortSampleRate = '48';
        menuSampleRate = '48 kHz';
        break;
    case '88200': 
        shortSampleRate = '88';
        menuSampleRate = '88.2 kHz';
        break;
    case '96000': 
        shortSampleRate = '96';
        menuSampleRate = '96 kHz';
        break;
    case '192000': 
        shortSampleRate = '192';
        menuSampleRate = '192 kHz';
        break;
    default: 
        shortSampleRate = sampleRate;
        menuSampleRate = sampleRate;
}

// Set bit depth to 24 Bit
const bitDepth = '24 Bit';
const shortBitDepth = '24b';

// Get the current date in YYMMDD format
const date = new Date();
const yy = String(date.getFullYear()).slice(-2);
const mm = String(date.getMonth() + 1).padStart(2, '0');
const dd = String(date.getDate()).padStart(2, '0');
const formattedDate = `${yy}${mm}${dd}_`;

// Step 3: Navigate to the "Bounce Mix" window and perform the additional steps
sf.ui.proTools.menuClick({
    menuPath: ["File", "Bounce Mix..."]
});
sf.ui.proTools.windows.whoseTitle.is("Bounce Mix").first.elementWaitFor();

// Set location to Session Folder
sf.ui.proTools.windows.whoseTitle.is("Bounce Mix").first.groups.whoseTitle.is("Location").first.radioButtons.whoseTitle.is("Session Folder:").first.elementClick();

// Enable Offline Bounce
sf.ui.proTools.windows.whoseTitle.is("Bounce Mix").first.checkBoxes.whoseTitle.is("Offline").first.checkboxSet({
    targetValue: "Enable",
});

// Disable Import After Bounce
sf.ui.proTools.windows.whoseTitle.is("Bounce Mix").first.groups.whoseTitle.is("Location").first.checkBoxes.whoseTitle.is("Import After Bounce").first.checkboxSet({
    targetValue: "Disable",
});

// Disable Add MP3
sf.ui.proTools.windows.whoseTitle.is("Bounce Mix").first.groups.whoseTitle.is("Audio").first.checkBoxes.whoseTitle.is("Add MP3").first.checkboxSet({
    targetValue: "Disable",
});

// Set File Format to Interleaved
sf.ui.proTools.windows.whoseTitle.is("Bounce Mix").first.groups.whoseTitle.is("Audio").first.popupButtons.allItems[1].popupMenuSelect({
    menuPath: ["Interleaved"],
});

// Set the Bit Depth to 24 Bit
sf.ui.proTools.windows.whoseTitle.is("Bounce Mix").first.groups.whoseTitle.is("Audio").first.popupButtons.allItems[2].popupMenuSelect({
    menuPath: [bitDepth],
});

// Set the Sample Rate in the Bounce Mix menu
sf.ui.proTools.windows.whoseTitle.is("Bounce Mix").first.groups.whoseTitle.is("Audio").first.popupButtons.allItems[3].popupMenuSelect({
    menuPath: [menuSampleRate],
});

// Step 4: Retrieve the file name and update it with the date, session name, "EAS MIX," sample rate, and bit depth
const bounceWindow = sf.ui.proTools.windows.whoseTitle.is("Bounce Mix").first;
const fileNameField = bounceWindow.textFields.first;

// Check if fileNameField.value is null or not
if (fileNameField && fileNameField.value) {
    let currentFileName = fileNameField.value;

    // Update the file name with the formatted information
    const updatedFileName = `${formattedDate}${sessionName}_EASMIX_${shortSampleRate}_${shortBitDepth}.wav`;

    // Ensure the text field is selected and set the new file name
    bounceWindow.textFields.first.elementSetTextFieldWithAreaValue({ value: updatedFileName });
}

// Change this to your preferred scale - "mini", "small", "medium", "large", "very large"
const preferredScale = "medium";

const tempPresetName = "TH_q3q4_Convert";
const tempMarkerName = "Q3_Q4 Temp Marker";
const tempMemLocNum = 25001;
const sessionAppendix = "_q3q4Convert";
const showQ4WindowSizeWarning = false;
let singleInstance = false;
let showCompletionDlg = false;
let lastSuccessfulScale = null;

const sessionPath = sf.ui.proTools.mainWindow.invalidate().sessionPath;
const sessionDirectory = sessionPath.split('/').slice(0, -1).join('/');

const pluginLookUpArray = [
    {
        oldPluginName: "FabFilter Pro-Q 3",
        newPluginName: "FabFilter Pro-Q 4",

        // Q4 paste position (MEDIUM only)
        pastePositionXPercentage: 0.69,
        pastePositionYPercentage: 0.18,

        // Q3 positions for different UI scales, in order of preference
        scalePositions: [
            {
                name: "mini",
                presetPositionXPercentage: 0.74,
                presetPositionYPercentage: 0.29,
            },
            {
                name: "small",
                presetPositionXPercentage: 0.715,
                presetPositionYPercentage: 0.225,
            },
            {
                name: "medium",
                presetPositionXPercentage: 0.69,
                presetPositionYPercentage: 0.20,
            },
            {
                name: "large",
                presetPositionXPercentage: 0.67,
                presetPositionYPercentage: 0.175,
            },
            {
                name: "very large",
                presetPositionXPercentage: 0.655,
                presetPositionYPercentage: 0.155,
            }
        ]
    },
];

// Function - Dismiss Missing Files Dialog
/**
 * @param {Object} obj
 * @param {"Skip All"|"Manually Find & Relink"|"Automatically Find & Relink"} obj.radioButton}
 */
function dismissMissingFilesDialog({ radioButton }) {
    const dlg = sf.ui.proTools.windows.whoseTitle.is("Missing Files").first;

    //Wait for dialog box to appear
    dlg.elementWaitFor({
        timeout: 300,
        pollingInterval: 10,
        onError: "Continue",
    });

    if (dlg.exists) {
        dlg.radioButtons.whoseTitle.is(radioButton).first.elementClick();
        dlg.buttons.whoseTitle.is("Ok").first.elementClick();

        dlg.elementWaitFor({
            waitType: "Disappear",
            timeout: 100,
            pollingInterval: 10,
            onError: "Continue",
        });
    }
}

function waitForPtSession() {
    sf.wait({ intervalMs: 500 })
    while (!sf.ui.proTools.getMenuItem('File', 'New...').isEnabled) {
        sf.wait({ intervalMs: 100 });
    }
    while (!sf.ui.proTools.invalidate().hasValidUI) {
        sf.wait({ intervalMs: 200 })
    }
}

function waitForSessionToOpen() {

    try {
        while (!sf.ui.proTools.getMenuItem('File', 'New...').isEnabled) {
            sf.wait({ intervalMs: 100 });
            // Ignore Missing I/O
            if (sf.ui.proTools.windows.whoseTitle.is("Session Notes").first.exists) {
                sf.ui.proTools.windows.whoseTitle.is("Session Notes").first.buttons.whoseTitle.is("No").first.elementClick();
                sf.ui.proTools.windows.whoseTitle.is("Session Notes").first.buttons.whoseTitle.is("No").first.elementWaitFor({ waitType: "Disappear" });
            }

            // Ignore Missing Plug-ins
            if (sf.ui.proTools.windows.whoseTitle.is("Missing AAX Plugins").first.exists) {
                sf.ui.proTools.windows.whoseTitle.is("Missing AAX Plugins").first.buttons.whoseTitle.is("OK").first.elementClick();
                sf.ui.proTools.windows.whoseTitle.is("Missing AAX Plugins").first.buttons.whoseTitle.is("OK").first.elementWaitFor({ waitType: "Disappear" });
            }

            // Dismiss missing files..."" dialog if it appears
            dismissMissingFilesDialog({
                radioButton: "Skip All",
            });

            // Dismiss generic alert
            if (sf.ui.proTools.windows.whoseDescription.is("alert").first.exists) {
                sf.ui.proTools.windows.whoseDescription.is("alert").first.getElement("AXDefaultButton").elementClick();
                sf.ui.proTools.windows.whoseDescription.is("alert").first.getElement("AXDefaultButton").elementWaitFor({ waitType: "Disappear" });
            }
            sf.wait({ intervalMs: 200 });
        }
    }
    catch (ex) {
        sf.wait({ intervalMs: 500 });
        while (sf.ui.proTools.invalidate().windows.filter(w => w.title.value.match(/^(Edit:|Mix:)/)).length.valueOf() === null) {
            // Ignore Missing I/O
            if (sf.ui.proTools.windows.whoseTitle.is("Session Notes").first.exists) {
                sf.ui.proTools.windows.whoseTitle.is("Session Notes").first.buttons.whoseTitle.is("No").first.elementClick();
                sf.ui.proTools.windows.whoseTitle.is("Session Notes").first.buttons.whoseTitle.is("No").first.elementWaitFor({ waitType: "Disappear" });
            }

            // Ignore Missing Plug-ins
            if (sf.ui.proTools.windows.whoseTitle.is("Missing AAX Plugins").first.exists) {
                sf.ui.proTools.windows.whoseTitle.is("Missing AAX Plugins").first.buttons.whoseTitle.is("OK").first.elementClick();
                sf.ui.proTools.windows.whoseTitle.is("Missing AAX Plugins").first.buttons.whoseTitle.is("OK").first.elementWaitFor({ waitType: "Disappear" });
            }

            // Dismiss missing files..."" dialog if it appears
            dismissMissingFilesDialog({
                radioButton: "Skip All",
            });

            // Dismiss generic alert
            if (sf.ui.proTools.windows.whoseDescription.is("alert").first.exists) {
                sf.ui.proTools.windows.whoseDescription.is("alert").first.getElement("AXDefaultButton").elementClick();
                sf.ui.proTools.windows.whoseDescription.is("alert").first.getElement("AXDefaultButton").elementWaitFor({ waitType: "Disappear" });
            }
            sf.wait({ intervalMs: 200 });
        }
    }
}

function ensureEditWindowIsFocused() {
    //ensure edit window is focused
    sf.ui.proTools.menuClick({ menuPath: ['Window', 'Edit'] });
}

function ensureTempoRulerIsVisible() {
    //ensure tempo ruler is visible
    sf.ui.proTools.menuClick({
        menuPath: ["View", "Rulers", "Tempo"],
        targetValue: "Enable",
    });
}

function ensureAllInsertSlotsVisible() {
    sf.ui.proTools.menuClick({
        menuPath: ["View", "Edit Window Views", "Inserts A-E"],
        targetValue: "Enable",
    });

    sf.ui.proTools.menuClick({
        menuPath: ["View", "Edit Window Views", "Inserts F-J"],
        targetValue: "Enable",
    });
}

function hideAllFloatingWindows() {
    //Hide all floating windows
    sf.ui.proTools.menuClick({
        menuPath: ["Window", "Hide All Floating Windows"],
        targetValue: "Enable",
    });
}

function enableTransportCluster() {

    sf.ui.proTools.mainWindow.invalidate();

    const transportCluster = sf.ui.proTools.mainWindow.transportViewCluster;
    const mainTransportPlayButton = transportCluster.getFirstWithTitle('Normal Transport Buttons');

    //Check if MIDI Controls Cluster is visible and if not open it.
    if (!mainTransportPlayButton.exists) {
        //Open the Toolbar Options Menu
        sf.ui.proTools.mainWindow.toolbarOptionsMenuButton.elementClick();

        const zoomControls = sf.ui.proTools.windows.whoseTitle.endsWith("Zoom Controls").first;

        //Wait for the Toolbar Options Menu to be open (by waiting for first menu Item)
        zoomControls.elementWaitFor();

        //Enable MIDI Controls
        zoomControls.menuItems.whoseTitle.is("Transport").first.elementClick();

        //Close the Toolbar Options Menu
        sf.ui.proTools.appActivateMainWindow();

        //The main window changed because the midi cluster was added,
        //so invalidate the main window
        sf.ui.proTools.mainWindow.invalidate();
    }
}

/** @param {{ savePath: string, newSessionName: string }} args */
function saveAs({ savePath, newSessionName }) {

    if (sf.file.exists({ path: sessionDirectory + '/' + newSessionName + ".ptx" }).exists) {
        sf.file.delete({ path: sessionDirectory + '/' + newSessionName + ".ptx" })
    }

    sf.app.proTools.saveSessionAs({
        sessionPath: sessionDirectory + '/' + newSessionName + ".ptx"
    });

}

function getNextVersionNumber(filePath) {
    let version = 1;
    let versionedPath = filePath;

    while (sf.file.exists({ path: versionedPath }).exists) {
        version++;
        // Split only the last extension
        const lastDotIndex = filePath.lastIndexOf('.');
        const basePath = filePath.substring(0, lastDotIndex);
        const ext = filePath.substring(lastDotIndex + 1);
        versionedPath = `${basePath}_v${version}.${ext}`;
    }

    return versionedPath;
}

function ensureOldSessionsFolder(sessionParentPath) {
    const oldSessionsPath = `${sessionParentPath}/Old Sessions`;

    if (!sf.file.directoryExists({ path: oldSessionsPath }).exists) {
        sf.file.directoryCreate({ path: oldSessionsPath });
    }

    return oldSessionsPath;
}

function moveToOldSessions(filePath, oldSessionsPath) {
    const fileName = filePath.split("/").slice(-1)[0];
    const newPath = `${oldSessionsPath}/${fileName}`;

    // If file already exists in Old Sessions, get next version number
    const finalPath = sf.file.exists({ path: newPath }).exists
        ? getNextVersionNumber(newPath)
        : newPath;

    sf.file.move({
        sourcePath: filePath,
        destinationPath: finalPath
    });
}

function removeExistingAppendix(sessionName, appendix) {
    // Remove the appendix if it already exists at the end of the filename
    if (sessionName.endsWith(appendix)) {
        return sessionName.slice(0, -appendix.length);
    }
    return sessionName;
}

function saveAsConvertSession() {
    sf.ui.proTools.appActivateMainWindow();
    sf.ui.proTools.mainWindow.invalidate();

    const sessionPath = sf.ui.proTools.mainWindow.invalidate().sessionPath;
    const sessionParentPath = sessionPath.split("/").slice(0, -1).join("/");
    const sessionFullName = sessionPath.split("/").slice(-1)[0];

    // Split only at the last period for the extension
    const lastDotIndex = sessionFullName.lastIndexOf('.');
    const sessionName = sessionFullName.substring(0, lastDotIndex);
    const extension = sessionFullName.substring(lastDotIndex + 1);

    // Remove existing appendix if present and add it once
    const cleanSessionName = removeExistingAppendix(sessionName, sessionAppendix);
    const newSessionName = `${cleanSessionName}${sessionAppendix}`;
    const newSessionPath = `${sessionParentPath}/${newSessionName}.${extension}`;

    // Check if file with appendix already exists
    if (sf.file.exists({ path: newSessionPath }).exists) {
        // Ensure Old Sessions folder exists and get its path
        const oldSessionsPath = ensureOldSessionsFolder(sessionParentPath);

        // Move existing file to Old Sessions
        moveToOldSessions(newSessionPath, oldSessionsPath);
    }

    // Now perform the save as operation with the corrected name
    saveAs({
        savePath: sessionParentPath,
        newSessionName: newSessionName,
    });
}

function findAllTracksWithQ3() {
    /**
     * @param {array} plugNames
     * @param {boolean} includeInactive
     */
    function selectTracksWithPlugName(plugNames, includeInactive) {

        let foundTracks = [];
        const notificationID = sf.system.newGuid().guid;

        // Filter for only visible tracks first
        const visibleTracks = sf.app.proTools.tracks.invalidate().allItems.filter(track => !track.isHidden);

        // Loop through visible tracks
        visibleTracks.forEach((track, index) => {
            // Notify progress of scanning tracks
            sf.interaction.notify({
                uid: notificationID,
                title: "Scanning for Pro-Q 3",
                progress: (index + 1) / visibleTracks.length,
                message: `Scanning Track ${index + 1} of ${visibleTracks.length}: ${track.name}`,
            });

            // Skip inactive tracks if not including them
            if (track.isInactive && !includeInactive) return;

            // For the insert scanning, we still need to use the UI approach
            // as the new SDK doesn't yet provide direct access to insert information
            const trackUI = sf.ui.proTools.trackGetByName({ name: track.name }).track;

            // Loop insert buttons
            for (let i = 0; i < 9; i++) {
                const insertBtn = trackUI.insertButtons[i];
                if (!insertBtn.exists) break;
                const insertSelectorBtn = trackUI.insertSelectorButtons[i];

                let isInactive;
                includeInactive ? isInactive = false : isInactive = insertSelectorBtn.value.invalidate().value === "inactive";

                if (isInactive) continue;

                const plugName = insertBtn.value.invalidate().value;
                if (plugNames.includes(plugName)) {
                    foundTracks.push(track.name);
                    break; // Found a Q3 on this track, no need to check other inserts
                }
            }
        });

        // Final notification showing completion
        sf.interaction.notify({
            uid: notificationID,
            title: "Scan Complete",
            progress: 1,
            message: `Found ${foundTracks.length} tracks with Pro-Q 3`,
            keepAliveMs: 1000,
        });

        if (foundTracks.length === 0) {
            alert(`No active Pro-Q 3<>Pro-Q 4 compatible inserts or tracks found`);
            restoreAndDeleteTempMemoryLocation();
            throw 0;
        }

        sf.app.proTools.selectTracksByName({ trackNames: foundTracks });
    }

    /**
     * @param {object} param
     * @param {string[]} param.plugNames
     * @param {boolean} [param.includeInactive]
     */
    function selectTracksWithPlug_in({ plugNames, includeInactive = false }) {
        sf.ui.proTools.invalidate();

        // Get disabled views
        const disabled = ["Inserts A-E", "Inserts F-J"].filter(view =>
            !sf.ui.proTools.getMenuItem("View", "Edit Window Views", view).isMenuChecked
        );

        // Enable Disabled Views
        disabled.map(view =>
            sf.ui.proTools.menuClick({
                menuPath: ["View", "Edit Window Views", view],
                targetValue: "Enable"
            })
        );

        try {
            selectTracksWithPlugName(plugNames, includeInactive);
        } catch (err) {
            throw err;
        } finally {
            // Return Views to original state
            disabled.map(view =>
                sf.ui.proTools.menuClick({
                    menuPath: ["View", "Edit Window Views", view],
                    targetValue: "Disable"
                })
            );
        }
    }

    selectTracksWithPlug_in({
        plugNames: ["FabFilter Pro-Q 3"]
    });
}

function loadFirstPlugin() {

    function getInsertsInfo() {
        const insertInfo = Array(10).fill(0).map((_, index) => {

            const track = sf.ui.proTools.selectedTrack;

            const insertButton = track.invalidate().insertButtons[index];
            const insertButtonValue = insertButton.value.invalidate().value;

            const insertSelectorButton = track.invalidate().insertSelectorButtons[index]
            const insertSelectorButtonValue = insertSelectorButton.value.invalidate().value;

            return {
                insertButton,
                insertButtonValue,
                insertSelectorButton,
                insertSelectorButtonValue,
                insertIndex: index,
                pluginName: insertButtonValue,
                //isBypassed: insertSelectorButtonValue.includes('bypassed'),
                isActive: !insertSelectorButtonValue.includes('inactive'),
            };
        });

        return insertInfo;
    }

    //Get an array of usable plugin names
    const usablePluginNames = pluginLookUpArray.map(item => item.oldPluginName);

    const insertsInfo = getInsertsInfo();

    //Filter to get all insert slots whose name includes any of the usablePluginNames
    const matchingInsertSlots = insertsInfo.filter(btn => {
        return usablePluginNames.some((name) => name === btn.pluginName) && btn.isActive === true;
    });

    sf.ui.proTools.appActivateMainWindow();

    //Loop through the matchingInsertSlots
    matchingInsertSlots.forEach(insert => {

        sf.ui.proTools.selectedTrack.trackInsertToggleShow({
            insertNumber: insert.insertIndex + 1,
        });

        convertSettings();

    });

}

function convertSettings() {
    //position plugin window so drop down menu has room to drop
    // const targetWindowXPostion = sf.ui.proTools.mainWindow.buttons.whoseTitle.is("Add Tempo Change").first.frame.x;
    const targetWindowXPostion = sf.ui.proTools.mainWindow.cursorToolCluster.buttons.whoseTitle.is("Insertion Follows Playback").first.frame.x;
    const targetWindowYPosition = sf.ui.proTools.mainWindow.gridNudgeCluster.frame.y;

    const pluginWindow = sf.ui.proTools.windows.whoseTitle.contains("Plug-in:").first;
    pluginWindow.invalidate();

    if (pluginWindow.title.value !== "Plug-in: FabFilter Pro-Q 3") {
        throw ("The currently selected plugin is not FabFilter Q-3. Please select a Q3 instance and try again");
    }

    //get plugin bypass info - if bypass is active, then move on to the next instance
    const pluginBypassInfo = sf.ui.proTools.windows.whoseTitle.startsWith("Plug-in: FabFilter Pro-Q 3").first.buttons.whoseTitle.is("Effect Bypass").first.value.invalidate().value;

    if (pluginBypassInfo === "on") {
        return
    }

    function setWindowsizeAndPosition(settings) {
        const { window, x, y, screenIndex } = settings;
        let screenFrame = sf.ui.screens.allScreens[screenIndex].visibleFrame;

        window.windowMove({
            position: { x, y, }
        });
    }

    setWindowsizeAndPosition({
        window: pluginWindow,
        x: targetWindowXPostion,
        y: targetWindowYPosition,
        screenIndex: 0,
    });

    pluginWindow.invalidate();
    const targetPluginName = sf.ui.proTools.windows.first.popupButtons.whoseTitle.startsWith('Plugin Selector').first.value.invalidate().value;
    const matchingPluginInfo = pluginLookUpArray.find(item => item.oldPluginName === targetPluginName);
    const pluginWindowFrame = pluginWindow.frame;

    function copySettings({ matchingPluginInfo }) {
        // MODIFIED: Reorder the scale positions based on preferredScale and lastSuccessfulScale
        function getOrderedScalePositions(scalePositions, preferredScale, lastSuccessfulScale) {
            // Create a new array to avoid modifying the original
            let orderedPositions = [...scalePositions];

            // If we have a preferred scale that's different from the last successful one
            if (preferredScale && preferredScale !== lastSuccessfulScale) {
                // Find the preferred scale position
                const preferredIndex = orderedPositions.findIndex(pos => pos.name === preferredScale);

                if (preferredIndex !== -1) {
                    // Move the preferred scale to the front
                    const preferredPos = orderedPositions.splice(preferredIndex, 1)[0];
                    orderedPositions.unshift(preferredPos);
                }
            }

            // If we have a last successful scale and it's different from the preferred scale
            if (lastSuccessfulScale && (!preferredScale || preferredScale !== lastSuccessfulScale)) {
                // Find the last successful scale position (it might be at index 0 if it matched the preferred)
                const successfulIndex = orderedPositions.findIndex(pos => pos.name === lastSuccessfulScale);

                if (successfulIndex !== -1 && successfulIndex !== 0) {
                    // Move the last successful scale to the front (or second if preferred is first)
                    const successfulPos = orderedPositions.splice(successfulIndex, 1)[0];
                    if (preferredScale) {
                        // Insert after preferred
                        orderedPositions.splice(1, 0, successfulPos);
                    } else {
                        // Or at the beginning if no preferred
                        orderedPositions.unshift(successfulPos);
                    }
                }
            }

            return orderedPositions;
        }

        // Get the ordered scale positions
        const orderedScalePositions = getOrderedScalePositions(
            matchingPluginInfo.scalePositions,
            preferredScale,
            lastSuccessfulScale
        );

        // Try each scale position in sequence
        for (const scalePosition of orderedScalePositions) {
            try {
                // Get fresh window frame at start of each attempt
                const q3Window = sf.ui.proTools.windows.whoseTitle.contains("Plug-in: FabFilter Pro-Q 3").first;
                q3Window.invalidate();
                const freshPluginWindowFrame = q3Window.frame;

                const relativePresetButtonPosition = {
                    x: freshPluginWindowFrame.x + freshPluginWindowFrame.w * scalePosition.presetPositionXPercentage,
                    y: freshPluginWindowFrame.y + freshPluginWindowFrame.h * scalePosition.presetPositionYPercentage,
                };

                sf.mouse.setPosition({ position: relativePresetButtonPosition });
                sf.wait({ intervalMs: 200 });
                sf.mouse.click({ position: relativePresetButtonPosition, isControl: true });

                sf.keyboard.press({
                    keys: "down",
                    repetitions: 2,
                });

                sf.keyboard.press({
                    keys: "return",
                });

                // Delete existing preset if it exists
                if (sf.file.exists({
                    path: `~/Documents/FabFilter/Presets/Pro-Q 3/${tempPresetName}.ffp`,
                }).exists) {
                    sf.file.delete({
                        path: `~/Documents/FabFilter/Presets/Pro-Q 3/${tempPresetName}.ffp`,
                    });
                }

                // Wait for save window - this will throw an error if the click wasn't successful
                const saveWindow = sf.ui.proTools.windows.whoseTitle.is('Save').first;
                const saveWindowExists = saveWindow.elementWaitFor({
                    timeout: 500,
                    onError: "Continue"
                }).success;

                if (!saveWindowExists) {
                    throw new Error(`Save window did not appear for ${scalePosition.name} scale`);
                }

                // If we got here, the scale position worked
                sf.wait({ intervalMs: 200 });
                sf.ui.proTools.windows.whoseTitle.is("Save").first.textFields.first.elementSetTextAreaValue({
                    value: tempPresetName,
                });

                sf.wait({ intervalMs: 25 });
                saveWindow.buttons.whoseTitle.is("Save").first.elementClick();
                sf.wait({ intervalMs: 25 });
                saveWindow.elementWaitFor({ waitType: 'Disappear' });

                // If we get here, everything worked, so we can break the loop
                // Set default to be the current scalePosition
                lastSuccessfulScale = scalePosition.name
                return;

            } catch (error) {
                // If the last successful scale position was used, it means it failed
                if (lastSuccessfulScale === scalePosition.name) {
                    // Reset the last successful scale
                    lastSuccessfulScale = null;
                }

                // Continue to next scale position
                continue;
            }
        }

        // If we get here, none of the positions worked
        lastSuccessfulScale = null; // Reset last successful scale
        throw new Error("Failed to find working scale position for Pro-Q 3");
    }

    // Call copySettings with the correct parameters
    copySettings({
        matchingPluginInfo
    });


    //small wait to help
    sf.wait({ intervalMs: 200 });

    const pluginMenuItems = sf.ui.proTools.windows.first.popupButtons.whoseTitle.startsWith("Plugin Selector").first.popupMenuFetchAllItems().menuItems;
    const menuPath = pluginMenuItems.find(mi => mi.element.isMenuChecked).path;

    // More robust way to find the plugin item with width information
    const pluginItem = menuPath.find(item => item.includes('(stereo)') || item.includes('(mono)'));
    if (!pluginItem) {
        throw new Error("Could not find plugin with width information in menu path");
    }

    // Extract width and plugin name more safely
    const pluginWidth = pluginItem.match(/\(([^)]+)\)/)[0];
    const pluginBaseName = pluginItem.split(" (")[0];

    // Find the matching plugin object using the base name
    const matchingPluginObject = pluginLookUpArray.find(plugin => {
        return plugin.oldPluginName === pluginBaseName;
    });

    if (!matchingPluginObject) {
        throw new Error(`No matching plugin found for ${pluginBaseName}`);
    }

    // Create the new plugin name
    const newPluginName = `${matchingPluginObject.newPluginName} ${pluginWidth}`;

    // Create new plugin path - always including "EQ" for Q4
    const newPluginPath = [
        menuPath[0],           // "multichannel plugin" - always first
        "EQ",                  // Always insert "EQ" for Q4
        newPluginName         // The new plugin name with width
    ];

    sf.ui.proTools.appActivateMainWindow();

    function pasteSettings() {

        const q4Window = sf.ui.proTools.windows.whoseTitle.contains("Plug-in: FabFilter Pro-Q 4").first;

        // help to wait for any potential dialogs
        sf.wait({ intervalMs: 200 });

        // if a dialog appears, it means the plugin had automation
        if (sf.ui.proTools.confirmationButtonDialog.exists) {
            sf.ui.proTools.confirmationButtonDialog.buttons.whoseTitle.is("Cancel").first.elementClick();
            sf.ui.proTools.confirmationButtonDialog.elementWaitFor({ waitType: "Disappear" });
            return;
        }

        q4Window.elementWaitFor({
            waitType: "Appear",
        });

        // Get fresh frame data after window appears
        q4Window.invalidate();
        const q4WindowFrame = q4Window.frame;

        // Calculate position using new frame
        const relativePasteButtonPosition = {
            x: q4WindowFrame.x + q4WindowFrame.w * matchingPluginInfo.pastePositionXPercentage,
            y: q4WindowFrame.y + q4WindowFrame.h * matchingPluginInfo.pastePositionYPercentage
        }

        sf.mouse.setPosition({
            position: relativePasteButtonPosition,
        });

        sf.mouse.click({
            position: relativePasteButtonPosition,
        });

        sf.keyboard.type({
            text: tempPresetName,
        });

        sf.wait({ intervalMs: 200 });

        sf.keyboard.press({
            keys: "return",
            repetitions: 2,
        });

        sf.wait({ intervalMs: 200 });
    }

    function unlinkedMultiMono() {
        /////MULTI MONO STUFF/////
        const masterLink = sf.ui.proTools.windows.whoseTitle.contains("Plug-in: FabFilter Pro-Q 3").first.buttons.whoseTitle.is("Master Link button");
        const targetInsertSlot = sf.ui.proTools.windows.whoseTitle.contains("Plug-in: FabFilter Pro-Q 3").first.popupButtons.allItems[4].value.invalidate().value;

        const linkStatus = masterLink.first.value.invalidate().value;

        const pluginWin = sf.ui.proTools.windows.whoseTitle.contains("Plug-in:").first;

        //open multimono plugin instance
        function convertMultiMonoQ3toQ4() {
            pluginWin.popupButtons.allItems[5].popupMenuSelect({
                menuPath: newPluginPath,
            });
        }

        //duplicate current track
        function duplicateTrack() {
            sf.ui.proTools.menuClick({
                menuPath: ["Track", "Duplicate..."],
            });

            //Wait for Dialog
            sf.ui.proTools.duplicateTracksDialog

            //duplicate settings
            sf.ui.proTools.trackDuplicateSelected({
                duplicateActivePlaylist: false,
                duplicateAlternatePlaylists: false,
                duplicateAutomation: false,
                duplicateGroupAssignments: false,
                duplicateInserts: true,
                duplicateSends: false,
                insertAfterLastSelectedTrack: true,
                numberOfDuplicates: 1
            })

            //Wait for dlg to disappear
            sf.ui.proTools.duplicateTracksDialog.elementWaitFor({
                waitType: "Disappear",
            });

            const isThereAnAlertWindow = sf.ui.proTools.windows.whoseDescription.is("alert").first.elementWaitFor({
                timeout: 1000,
                onError: "Continue",
            }).success

            if (isThereAnAlertWindow) {
                sf.wait({ intervalMs: 200 });
                sf.ui.proTools.windows.whoseDescription.is("alert").first.getElement("AXDefaultButton").elementClick();
            }

            //wait for main window become active
            sf.wait({ intervalMs: 200 });
        }

        function openTargetInsertSlot() {
            var currentInsertSlot = sf.ui.proTools.windows.whoseTitle.startsWith("Plug-in: FabFilter Pro-Q").first.popupButtons.allItems[5].value.invalidate().value;

            const insertSlotsByLetter = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"];
            var letter = currentInsertSlot;
            var insertByNumber = insertSlotsByLetter.indexOf(letter) + 1;

            sf.ui.proTools.selectedTrack.trackInsertToggleShow({
                insertNumber: insertByNumber,
                targetValue: "Enable",
                waitForInsertWindow: true,
            });
        }

        //L or R channel focused
        //copy left channel
        function focusLeftChannel() {
            if (pluginWin.popupButtons.allItems[4].value.invalidate().value !== "L") {
                pluginWin.popupButtons.allItems[4].popupMenuSelect({
                    menuPath: ["Left"],
                });
            }
        }

        //copy right channel
        function focusRightChannel() {
            if (pluginWin.popupButtons.allItems[4].value.invalidate().value !== "R") {
                pluginWin.popupButtons.allItems[4].popupMenuSelect({
                    menuPath: ["Right"],
                });
            }
        }

        function selectTrackAbove() {
            sf.ui.proTools.menuClick({
                menuPath: ["Edit", "Selection", "Extend Edit Up"],
            });

            sf.ui.proTools.menuClick({
                menuPath: ["Edit", "Selection", "Remove Edit from Bottom"],
            });
        }

        function selectTrackBelow() {
            sf.ui.proTools.menuClick({
                menuPath: ["Edit", "Selection", "Extend Edit Down"],
            });

            sf.ui.proTools.menuClick({
                menuPath: ["Edit", "Selection", "Remove Edit from Top"],
            });
        }

        function deleteSelectedTrack() {
            if (sf.ui.proTools.getMenuItem('Track', 'Delete...').exists) {
                sf.ui.proTools.getMenuItem('Track', 'Delete...').elementClick();
                sf.ui.proTools.confirmationDialog.invalidate().elementWaitFor();
                sf.ui.proTools.confirmationDialog.buttons.whoseTitle.is('Delete').first.elementClick();
            } else if (sf.ui.proTools.getMenuItem('Track', 'Delete').exists) {
                sf.ui.proTools.getMenuItem('Track', 'Delete').elementClick();
            }
        }

        focusLeftChannel();

        duplicateTrack();

        openTargetInsertSlot();

        focusLeftChannel();

        copySettings({
            matchingPluginInfo
        });

        selectTrackAbove();

        openTargetInsertSlot();

        //launch new/replacement plugin multimono instance
        sf.ui.proTools.windows.whoseTitle.startsWith("Plug-in:").first.popupButtons.allItems[6].popupMenuSelect({
            menuPath: newPluginPath,
        });

        sf.ui.proTools.windows.whoseTitle.contains("Plug-in:").first.buttons.whoseTitle.is("Master Link button").first.invalidate();

        sf.ui.proTools.windows.whoseTitle.contains("Plug-in:").first.buttons.whoseTitle.is("Master Link button").first.elementClick();

        pasteSettings();

        selectTrackBelow();

        openTargetInsertSlot();

        focusRightChannel();

        copySettings({
            matchingPluginInfo
        });

        selectTrackAbove();

        openTargetInsertSlot();

        focusRightChannel();

        pasteSettings();

        //store originally selected track name
        const selectedTracks = sf.ui.proTools.selectedTrackNames

        selectTrackBelow();

        deleteSelectedTrack();

        // select original track name
        sf.app.proTools.selectTracksByName({ trackNames: selectedTracks });
    }

    //load new/replacement Version
    if (menuPath[0] === "multi-mono plugin" && sf.ui.proTools.windows.whoseTitle.contains("Plug-in: FabFilter Pro-Q").first.buttons.whoseTitle.is("Master Link button").first.value.invalidate().value === "") {
        //selects multi-mono instance unlinked
        alert("Unlinked Multi-mono is currently not supported, aborting script now");
        throw 0;
        unlinkedMultiMono();
    } else if (menuPath[0] === "multi-mono plugin") {
        //selects multi-mono instance
        sf.ui.proTools.windows.whoseTitle.startsWith("Plug-in:").first.popupButtons.allItems[6].popupMenuSelect({
            menuPath: newPluginPath,
        });

        pasteSettings();
    } else {
        //selects multichannel or individual instance
        sf.ui.proTools.windows.whoseTitle.startsWith("Plug-in:").first.popupButtons.allItems[5].popupMenuSelect({
            menuPath: newPluginPath,
        });
        pasteSettings();
    }

    if (!singleInstance) {
        //Close plugin window
        sf.ui.proTools.menuClick({
            menuPath: ["Window", "Hide All Floating Windows"],
            targetValue: "Enable",
        });
    }
}

function scrollToTrack(trackName) {
    var confirmationDialog = sf.ui.proTools.confirmationDialog;
    var scrollTrack = (typeof trackName == "object") ? trackName[0] : trackName;

    try {
        sf.ui.proTools.menuClick({ menuPath: ['Track', 'Scroll to Track...'] });
        confirmationDialog.elementWaitFor({ timeout: 100 });
    } catch (err) {
        sf.keyboard.press({ keys: "n", repetitions: 2 });
        sf.ui.proTools.menuClick({ menuPath: ['Track', 'Scroll to Track...'] });
        confirmationDialog.elementWaitFor({}, `Could not find Scroll to track Dialog`);
    }

    try {
        confirmationDialog.textFields.first.elementSetTextFieldWithAreaValue({
            value: scrollTrack,
        });
        confirmationDialog.buttons.whoseTitle.is('OK').first.elementClick();
        confirmationDialog.elementWaitFor({ waitType: 'Disappear' }, `Could not find track named ${trackName}`);
    } catch (err) {
        sf.keyboard.press({ keys: "alt+backspace", repetitions: 2 });
        sf.wait({ intervalMs: 100 });
        sf.keyboard.type({ text: scrollTrack });
        confirmationDialog.buttons.whoseTitle.is('OK').first.elementClick();
    }
}

function setTrackHeights() {
    var size = 'small';

    sf.ui.proTools.appActivate();

    const firstTrack = sf.ui.proTools.visibleTrackNames[0];

    // Scroll to Track
    scrollToTrack(firstTrack);

    var f = sf.ui.proTools.selectedTrack.frame;

    sf.keyboard.press({ keys: "left" })

    var popupMenu = sf.ui.proTools.selectedTrack.popupMenuOpenFromElement({
        anchor: "TopLeft",
        relativePosition: { x: f.w - 10, y: 5 },
        isOption: true,
    }).popupMenu;
    popupMenu.menuClickPopupMenu({
        menuPath: [size]
    });
}

function selectAndOpenAllTrackFolders() {
    const tracks = sf.app.proTools.tracks.invalidate().allItems;

    const folderTrackNames = tracks
        .filter(track => ["BasicFolder", "RoutingFolder"].includes(track.type))
        .map(track => track.name);

    // Open all Folder tracks
    sf.app.proTools.setTrackOpenState({
        trackNames: folderTrackNames,
        enabled: true
    });

}

function storeTrackVisibility() {

    sf.ui.proTools.invalidate();

    // check if memory location already exists and delete if so
    const number = sf.app.proTools.memoryLocations.invalidate().allItems.map(t => t.number)
    if (number.includes(tempMemLocNum)) {
        sf.app.proTools.clearMemoryLocations({
            numbers: [tempMemLocNum],
        });

        sf.app.proTools.memoryLocations.invalidate();

        // small wait to help give memory location cache time to update
        sf.wait({ intervalMs: 500 });
    }

    sf.app.proTools.createMemoryLocation({
        colorIndex: 1,
        name: tempMarkerName,
        timeProperties: "None",
        groupEnables: true,
        zoomSettings: false,
        prePostRollTimes: false,
        trackVisibility: true,
        trackHeights: true,
        windowConfiguration: false,
        executionMode: "Foreground",
        number: tempMemLocNum,
    });

}

function restoreAndDeleteTempMemoryLocation() {

    // Restore original track visibility
    sf.ui.proTools.memoryLocationsGoto({
        memoryLocationNumber: tempMemLocNum,
    });

    var numbersToDelete = [tempMemLocNum];

    sf.app.proTools.clearMemoryLocations({
        numbers: numbersToDelete,
    });

}

function setq4WindowSizePrompt() {

    sf.interaction.displayDialog({
        buttons: ["OK", "Cancel"],
        cancelButton: "Cancel",
        title: "Tristan Hoogland's FabFilter Pro-Q 3 to Pro-Q 4 Converter",
        prompt: "KEEP THIS DIALOG OPEN!!" + ("\n") + ("\n") + "Before proceeding, open a single instance (an existing one or new instantiation is fine) of Q4 and set the window scale to MEDIUM." + ("\n") + ("\n") + "Once complete, press OK.",
    });

    hideAllFloatingWindows();

}

function tempPresetFileCheck() {

    const filePath = `~/Documents/FabFilter/Presets/Pro-Q 3/${tempPresetName}.ffp`;

    // check if preset file exists before proceeding, if not we'll need to reload protools to clear the cache of Q4 so it can see the file correctly
    if (!sf.file.exists({
        path: filePath,
    }).exists) {

        const presetFileCheckDlg = sf.interaction.displayDialog({
            buttons: ["Yes", "Cancel"],
            cancelButton: "Cancel",
            defaultButton: "Yes",
            prompt: "Welcome to my FabFilter Pro-Q 3 to Pro-Q 4 converter!" + ("\n") + ("\n") + "Before proceeding we need to create a temporary preset file and reload your session. We only need to do this once EVER, and you won't see this prompt again." + ("\n") + ("\n") + "Proceed?",
            title: "Tristan Hoogland's FabFilter-Pro Q 3 to Pro-Q 4 Converter",
        }).button;

        // Create empty file
        sf.file.writeText({
            path: filePath,
            text: "",  // Empty array for blank file, or [''] for file with single empty line
        });

        // Let's give the system time to write the file correctly
        sf.wait({ intervalMs: 1000 });

        // Verify file exists
        if (!sf.file.exists({ path: filePath })) {
            log(`Failed to create the file: ${filePath}`);
        } else {
            log(`File successfully written: ${filePath}`);
        }

        sf.app.proTools.closeSessionSavingFirst();

        sf.app.proTools.openSession({
            sessionPath: sessionPath,
        })

        waitForSessionToOpen();

    }

}

//MAIN FUNCTION
function main() {

    if (!sf.ui.proTools.isRunning) {
        sf.interaction.notify({
            title: "ProTools is not runnning" + ("\n") + "Launch PT and try again",
        });
        throw 0
    }

    if (!sf.ui.proTools.getMenuItem('Window', 'Edit').isEnabled) {
        sf.interaction.notify({
            title: "ProTools is not runnning" + ("\n") + "Launch PT and try again",
        });
        throw 0
    }

    sf.ui.proTools.appActivateMainWindow();
    sf.ui.proTools.mainWindow.invalidate();

    // This should only ever need to run once
    tempPresetFileCheck();

    const conversionType = sf.interaction.selectFromList({
        items: ["Single Instance", "Selected Tracks", "Entire Session"],
        title: "Tristan Hoogland's FabFilter Pro-Q 3 to Pro-Q 4 Converter",
        prompt: "What Pro-Q 3 to Pro-Q 4 conversion type do you want?",
        defaultItems: ["Single Instance"],
        onCancel: "Abort",
    }).list[0];

    if (conversionType === "Single Instance") {
        singleInstance = true;
        convertSingleInstance();
    } else if (conversionType === "Selected Tracks") {
        showCompletionDlg = true;
        convertSelectedTracks();
    } else if (conversionType === "Entire Session") {
        showCompletionDlg = true;
        convertEntireSession();
    }

    function convertSingleInstance() {

        if (showQ4WindowSizeWarning) {
            setq4WindowSizePrompt();
        }

        ensureEditWindowIsFocused();

        ensureTempoRulerIsVisible();

        // Check if a Pro-Q 3 window is open
        const proQ3Window = sf.ui.proTools.windows.whoseTitle.startsWith("Plug-in: FabFilter Pro-Q 3").first;

        if (!proQ3Window.exists) {
            sf.interaction.displayDialog({
                buttons: ["OK", "Cancel"],
                cancelButton: "Cancel",
                defaultButton: "OK",
                prompt: "Open the Pro-Q 3 plugin you'd like to convert then press OK.",
                title: "Pro-Q 3 Not Found"
            });
        }

        proQ3Window.invalidate();

        if (!proQ3Window) {
            throw 0;
        }

        //get open plugin focused
        function focusOpenPlugin() {
            var frontPluginWin = sf.ui.proTools.getFloatingWindowWithTitleStartingWith("Plug-in: FabFilter").invalidate();
            var pluginTrack = frontPluginWin.popupButtons.whoseTitle.is("Track Selector").first.value.invalidate().value

            sf.ui.proTools.trackSelectByName({ names: [pluginTrack] });
        }

        focusOpenPlugin();

        convertSettings();

    }

    function convertSelectedTracks() {

        let selectedTracks;

        // Loop until tracks are selected or user cancels
        while (true) {
            selectedTracks = sf.ui.proTools.selectedTrackNames;

            if (selectedTracks.length > 0) {
                break; // Exit loop if tracks are selected
            }

            const response = sf.interaction.displayDialog({
                buttons: ["OK", "Cancel"],
                prompt: "No tracks selected. Make a selection and click OK",
                title: "No Tracks Selected",
                cancelButton: "Cancel",
            }).button;

            if (response === "Cancel") {
                return; // Exit the entire function if user cancels
            }
        }

        setq4WindowSizePrompt();

        // Rest of function continues only if tracks are selected
        ensureEditWindowIsFocused();

        sf.app.proTools.saveSession();

        saveAsConvertSession();

        storeTrackVisibility();

        hideAllFloatingWindows();

        ensureTempoRulerIsVisible();

        ensureAllInsertSlotsVisible();

        setTrackHeights();

        enableTransportCluster();

        selectAndOpenAllTrackFolders();

        sf.ui.proTools.trackSelectByName({ names: selectedTracks, deselectOthers: true });

        function doForAllSelectedTracks(action) {

            const originallySelectedTrackNames = sf.ui.proTools.selectedTrackNames;
            const totalTracks = originallySelectedTrackNames.length;
            const notificationID = sf.system.newGuid().guid;

            try {
                sf.ui.proTools.selectedTrackHeaders.forEach((track, index) => {
                    // Update progress notification
                    sf.interaction.notify({
                        uid: notificationID,
                        title: "Converting Pro-Q 3 to Pro-Q 4",
                        progress: (index + 1) / totalTracks,
                        message: `Converting Track ${index + 1} of ${totalTracks}: ${track.normalizedTrackName}\nRemaining: ${totalTracks - (index + 1)} tracks`,
                        keepAliveMs: 5000
                    });

                    track.trackSelect();
                    action(track);
                });
            }
            finally {
                sf.app.proTools.selectTracksByName({ trackNames: originallySelectedTrackNames });
            }
        }

        /**@param {AxPtTrackHeader} track */
        function trackFunc(track) {
            loadFirstPlugin();
        }

        doForAllSelectedTracks(trackFunc);
    }

    function convertEntireSession() {

        sf.interaction.displayDialog({
            buttons: ["Yes", "Cancel"],
            cancelButton: "Cancel",
            defaultButton: "Yes",
            prompt: "You are about to find and replace ALL active instances of FabFilter Pro-Q 3 with Pro-Q 4. This may take some time." + ("\n") + ("\n") + "Are you sure you want to continue?",
            title: "Tristan Hoogland's FabFilter-Pro Q 3 to Pro-Q 4 Converter",
        }).button;

        ensureEditWindowIsFocused();

        sf.app.proTools.saveSession();

        setq4WindowSizePrompt();

        saveAsConvertSession();

        storeTrackVisibility();

        hideAllFloatingWindows();

        ensureTempoRulerIsVisible();

        ensureAllInsertSlotsVisible();

        setTrackHeights();

        enableTransportCluster();

        selectAndOpenAllTrackFolders();

        findAllTracksWithQ3();

        function doForAllSelectedTracks(action) {
            const originallySelectedTrackNames = sf.ui.proTools.selectedTrackNames;
            const totalTracks = originallySelectedTrackNames.length;
            const notificationID = sf.system.newGuid().guid;

            try {
                sf.ui.proTools.selectedTrackHeaders.forEach((track, index) => {
                    // Update progress notification
                    sf.interaction.notify({
                        uid: notificationID,
                        title: "Converting Pro-Q 3 to Pro-Q 4",
                        progress: (index + 1) / totalTracks,
                        message: `Converting Track ${index + 1} of ${totalTracks}: ${track.normalizedTrackName}\nRemaining: ${totalTracks - (index + 1)} tracks`,
                        keepAliveMs: 5000
                    });

                    track.trackSelect();
                    action(track);
                });
            }
            finally {
                sf.ui.proTools.trackSelectByName({ names: originallySelectedTrackNames });
            }
        }

        /**@param {AxPtTrackHeader} track */
        function trackFunc(track) {

            loadFirstPlugin();

        }

        doForAllSelectedTracks(trackFunc);

        //finally deselect all tracks
        sf.ui.proTools.trackDeselectAll();

        sf.app.proTools.saveSession();

    }

    if (conversionType === "Selected Tracks" || conversionType === "Entire Session") {
        restoreAndDeleteTempMemoryLocation();
    }

    if (showCompletionDlg) {
        sf.interaction.displayDialog({
            prompt: "FabFilter-Pro Q 3 to Pro-Q 4 conversion complete!"
        })
    }

}

main();
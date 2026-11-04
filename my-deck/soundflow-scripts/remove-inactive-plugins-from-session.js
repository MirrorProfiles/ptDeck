function closeDialog() {
    const titles = ['Remove', 'Change'];
    titles.forEach(title => {
        if (sf.ui.proTools.confirmationDialog.invalidate().buttons.whoseTitle.is(title).first.exists) {
            sf.ui.proTools.confirmationDialog.buttons.whoseTitle.is(title).first.elementClick();
            sf.ui.proTools.confirmationDialog.elementWaitFor({ waitType: "Disappear" });
        }
    });
}

function scrollToTrackNamed(trackName, selectedTracks) {
    // Open scroll to track dialog and enter track name
    sf.ui.proTools.menuClick({ menuPath: ['Track', 'Scroll to Track...'] });
    var confirmationDialogWin = sf.ui.proTools.confirmationDialog;

    confirmationDialogWin.elementWaitFor();

    confirmationDialogWin.textFields.first.elementSetTextFieldWithAreaValue({ value: trackName });

    confirmationDialogWin.buttons.whoseTitle.is('OK').first.elementClick();

    confirmationDialogWin.elementWaitFor({ waitType: 'Disappear' });

    //Re-select originally selected tracks
    sf.ui.proTools.trackSelectByName({ names: selectedTracks })
};

function getTrackOutput(track) {
    sf.ui.proTools.appActivateMainWindow();

    const outputPathButton = track.outputPathButton;

    const outputPath = outputPathButton.title.value.split("\n").slice(-1)[0];
    return outputPath
}

function findInactiveItems(tracks) {
    let map = { inserts: {}, sends: {} };
    let elements = { inserts: [], sends: [] };

    tracks.forEach(track => {
        if (track) {
            let trackOutputs = sf.ui.proTools.selectedTrackHeaders.map(track => getTrackOutput(track));
            if (!trackOutputs.includes("inactive")) {
                for (let i = 0; i < track.insertSelectorButtons.length; i++) {
                    const button = track.insertSelectorButtons[i];
                    if (button.exists && button.invalidate().value.value.startsWith("inactive")) {
                        const slot = i + 1;
                        if (!map.inserts[slot]) {
                            map.inserts[slot] = [];
                            elements.inserts.push(slot);
                        }
                        map.inserts[slot].push(track.normalizedTrackName);
                    }
                }

                for (let i = 0; i < track.sendSelectorButtons.length; i++) {
                    const button = track.sendSelectorButtons[i];
                    if (button.exists && button.invalidate().value.value.startsWith("inactive")) {
                        const slot = i + 1;
                        if (!map.sends[slot]) {
                            map.sends[slot] = [];
                            elements.sends.push(slot);
                        }
                        map.sends[slot].push(track.normalizedTrackName);
                    }
                }
            }

        }
    });

    return { map, elements };
}


function removeItems(names, type, slot) {

    //sf.keyboard.press({ keys: "home" });
    sf.ui.proTools.trackSelectByName({ names: names, deselectOthers: true });
    const original = sf.ui.proTools.selectedTrackNames;
    if (original.length > 0) {
        sf.ui.proTools.trackGetByName({ name: original[0] }).track.trackScrollToView();
    }

    sf.ui.proTools.trackSelectByName({ names: names, deselectOthers: true });
    sf.ui.proTools.selectedTrack.trackInsertOrSendSelect({
        insertOrSend: type,
        pluginNumber: parseInt(slot, 10),
        selectForAllSelectedTracks: true,
        pluginPath: type === 'Insert' ? ['no insert'] : ['no send']
    });
    sf.wait({ intervalMs: 500 });
    closeDialog();


}

function batchRemove(map, elements, option) {

    if (option === "both" || option === "plugins") {
        map.inserts = map.inserts || {};
        elements.inserts.forEach(slot => {
            if (map.inserts[slot]) {
                removeItems(map.inserts[slot], 'Insert', slot);
            }
        });
    }

    if (option === "both" || option === "sends") {
        map.sends = map.sends || {};
        elements.sends.forEach(slot => {
            if (map.sends[slot]) {
                removeItems(map.sends[slot], 'Send', slot);
            }
        });
    }
}

function setTrackSize(size) {

    const selectedTrackH = sf.ui.proTools.selectedTrackHeaders[0]
    const hasHeaderHeightPopup = selectedTrackH.frame.h <= 79


    try {
        selectedTrackH.popupMenuSelect({
            anchor: "MidRight",
            relativePosition: { x: - 10, y: 0 },
            menuPath: [size],
            isOption: true,
            onError: "Continue",
        })
    } catch (err) {
        // Try header left poput
        if (hasHeaderHeightPopup) {
            sf.ui.proTools.selectedTrack.popupButtons.allItems[2].popupMenuSelect({
                menuPath: ["Track Height", size],
                isOption: true,
            });
        };
    };
};

function activateProToolsMenus(menuOptions) {
    menuOptions.forEach(menuOption => {
        sf.ui.proTools.menuClick({
            menuPath: ["View", "Edit Window Views", menuOption],
            targetValue: "Enable"
        });
    });
}

const proToolsMenuOptions = ["Inserts A-E", "Inserts F-J", "Sends A-E", "Sends F-J"];

function selectAllVisibleTracks() {
    sf.ui.proTools.trackDeselectAll();

    const topOfEditWindow = sf.ui.proTools.mainWindow.timelineFocusButton.frame.y;

    const topTrack = sf.ui.proTools.visibleTrackHeaders.filter(h => h.frame.y >= topOfEditWindow)[0];

    topTrack.titleButton.mouseClickElement({ isOption: true });
}


function selectinitialSelectedTracks() {
    ////////// Reselect only visible Audio, Aux & Routing Folder Tracks (i.e. exlude MIDI and Basic Folder Tracks)
    // Get all selected track headers
    var allSelectedTrackHeaders = sf.ui.proTools.invalidate().trackGetSelectedTracks().trackHeaders;

    if (allSelectedTrackHeaders.length == 0) {
        var procSession = sf.interaction.displayDialog({
            buttons: ["Cancel", "Proceed"],
            defaultButton: 'Proceed',
            prompt: "No tracks selected, proceed with entire session?",
        }).button;
        if (procSession == 'Proceed') {
            selectAllVisibleTracks();

        } else throw 0;

        var allSelectedTrackHeaders = sf.ui.proTools.invalidate().trackGetSelectedTracks().trackHeaders;
    }

    //Filter to get only visible suitable tracks

    const allVisibleSelectedTrackNames = allSelectedTrackHeaders
        .filter(t => t != null && t.title.value.includes
            ('Inst Track') || t.title.value.includes("Audio Track") || t.title.value.includes("Aux Track") || t.title.value.includes('Routing Folder Track') || t.title.value.includes('Master Track'))
        .map(t => t.normalizedTrackName);

    //Select only previously selected visible audio tracks
    sf.ui.proTools.trackSelectByName({
        names: allVisibleSelectedTrackNames,
        deselectOthers: true
    });

    return allVisibleSelectedTrackNames
}


function getCurrentTrackHeight() {

    var selectedTrackHeight = sf.ui.proTools.selectedTrack.frame.h;

    var trackHeight = {
        "16": "micro",
        "23": "mini",
        "43": "small",
        "97": "medium",
        "192": "large",
        "300": "jumbo",
    };

    var trackSize;
    // return height name if there's an exact match
    if (selectedTrackHeight in trackHeight) {
        (selectedTrackHeight > 300) ? trackSize = "extreme" : trackSize = trackHeight[selectedTrackHeight];
        return trackSize
    } else {
        //if we're here then track is at a non-standard height so let's get closest standard value

        //Get track pixel heights into numeric array
        var standardHeights = Object.keys(trackHeight).map(i => +i) // the +i converts the numeric value into a string

        // define function for finding closest value in starndard height array as a constant
        // code found here: https://www.tutorialspoint.com/get-closest-number-out-of-array-javascript
        const closestHeight = (arr, num) => {
            return arr.reduce((acc, val) => {
                if (Math.abs(val - num) < Math.abs(acc)) {
                    return val - num;
                } else {
                    return acc;
                }
            }, Infinity) + num;
        };
        // Return closest standard height
        return trackHeight[closestHeight(standardHeights, selectedTrackHeight)]
    };
};

function finishedTheJob(job) {
    sf.interaction.displayDialog({
        prompt: job,
        giveUpAfterSeconds: 1
    });
};

function startScript() {
    sf.ui.proTools.appActivateMainWindow();

    const userSelection = sf.interaction.selectFromList({
        items: [
            "Remove all Inactive Plugins and Sends",
            "Remove all Inactive Plugins",
            "Remove all Inactive Sends"
        ],
        allowMultipleSelections: false,
        prompt: "Choose what you want removed",
        title: "Inactive Cleaner"

    }).list;

    if (userSelection.length === 0) {
        alert("No option selected. Exiting script.");
        return;
    }

    let chosenOption = userSelection[0];

    sf.ui.proTools.mainWindow.invalidate();

    const wasLinked = sf.ui.proTools.getMenuItem('Options', 'Link Track and Edit Selection').isMenuChecked;
    if (wasLinked) {
        sf.ui.proTools.menuClick({
            menuPath: ["Options", "Link Track and Edit Selection"],
        });
    }

    const isEditWindowFocused = sf.ui.proTools.mainWindow.title.invalidate().value.startsWith("Edit: ");
    if (!isEditWindowFocused) {
        sf.ui.proTools.menuClick({ menuPath: ["Window", "Edit"] });
    }

    activateProToolsMenus(proToolsMenuOptions);


    sf.ui.proTools.invalidate();
    let origTrackHeight = getCurrentTrackHeight()

    try {
        var firstSelection = sf.ui.proTools.selectedTrackNames;

        let initialSelectedTracks = selectinitialSelectedTracks()
        //log(tracksForProcessing)
        let tracksForProcessing = sf.ui.proTools.selectedTrackHeaders;



        if (tracksForProcessing.length != 0) {
            sf.ui.proTools.trackGetByName({ name: tracksForProcessing[0].normalizedTrackName }).track.trackScrollToView();
            sf.ui.proTools.trackSelectByName({ names: initialSelectedTracks })
            setTrackSize('small');
        }
        else if (tracksForProcessing.length == 0) {
            const confirmVisibleTracks = confirm("No tracks are selected. Would you like to proceed with all visible tracks?");
            if (!confirmVisibleTracks) {
                alert("Operation cancelled.");
                throw 0;
            }

            firstSelection = sf.ui.proTools.visibleTrackNames;
            sf.ui.proTools.trackGetByName({ name: firstSelection[0] }).track.trackScrollToView();
            sf.ui.proTools.trackSelectByName({ names: firstSelection })
            setTrackSize('small');
        }

        log("Analysing session for inactive plugins/sends. Please wait.");

        const { map, elements } = findInactiveItems(tracksForProcessing);

        log("Analysis complete. Proceeding.");

        if (elements.inserts.length === 0 && elements.sends.length === 0) {
            alert("No inactive plugins or sends found.");
            return;
        }

        let option;
        if (chosenOption === "Remove all Inactive Plugins and Sends") {
            option = "both";
        } else if (chosenOption === "Remove all Inactive Plugins") {
            if (elements.inserts.length === 0) {
                alert("No inactive plugins found.");
                return;
            }
            option = "plugins";
        } else if (chosenOption === "Remove all Inactive Sends") {
            if (elements.sends.length === 0) {
                alert("No inactive sends found.");
                return;
            }
            option = "sends";
        }

        batchRemove(map, elements, option);

        if (wasLinked) {
            sf.ui.proTools.menuClick({
                menuPath: ["Options", "Link Track and Edit Selection"],
            });
        }
    }
    catch (err) {
        //Handle the error
        //log('Could not remove plugins/sends');
        finishedTheJob("No plugins or sends removed due to error")
    }

    sf.ui.proTools.trackSelectByName({ names: firstSelection, deselectOthers: true });
    setTrackSize(origTrackHeight)
    scrollToTrackNamed(firstSelection[0], firstSelection)
    finishedTheJob("Operation Completed")
}

startScript()
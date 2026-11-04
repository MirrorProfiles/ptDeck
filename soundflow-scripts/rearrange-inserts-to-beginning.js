


function waitForResponsive(timeout) {
    var pollingInterval = 200;
    var waitedTime = 0;
    while (true) {
        sf.engine.checkForCancellation();
        try {
            var val = sf.ui.proTools.mainWindow.title.invalidate().value;
            return true;
        } catch (err) {
        }
        if (timeout > 0 && waitedTime >= timeout)
            throw 'Timeout in waiting for Pro Tools to become responsive';
        sf.wait({ intervalMs: pollingInterval });
        waitedTime += pollingInterval;
    }
}

function dragPlugin({ sourceIndex, destIndex }, currentInsertButtons) {

    let retries = 0;
    //try to move the plugin 3 times before giving up
    while (retries < 3) {
        //Get the original assignment just becasue, we don't really need it...
        let originalSourceAssignment = currentInsertButtons[sourceIndex].value.invalidate().value;
        let sourcePosition = currentInsertButtons[sourceIndex].position;
        let destPosition = currentInsertButtons[destIndex].position;
        sf.mouse.simulateDrag({
            startPosition: { x: (sourcePosition.x + 2), y: (sourcePosition.y + 5) },
            endPosition: { x: (destPosition.x + 2), y: (destPosition.y + 5) }
        });
        waitForResponsive(10000); //Allow for slow-instantiating plugins
        if (currentInsertButtons[sourceIndex].value.invalidate().value === 'unassigned') return true;
        retries++;
    }
    return false;

}


function getCurrentInsertName(insert) {
    return insert.value.invalidate().value
}

function setupScreen() {
    //Close all floating windows
    if (sf.ui.proTools.floatingWindows.exists) {
        sf.ui.proTools.viewCloseFloatingWindows();
    }

    //Make sure Inserts are visible in Edit window
    sf.ui.proTools.menuClick({
        menuPath: ["View", "Edit Window Views", "Inserts F-J"],
        targetValue: "Enable",
    });
    sf.ui.proTools.menuClick({
        menuPath: ["View", "Edit Window Views", "Inserts A-E"],
        targetValue: "Enable",
    });
}

function movePlugins(targetTrack) {

    sf.ui.proTools.trackSelectByName({ names: [targetTrack], deselectOthers: true });

    sf.ui.proTools.selectedTrack.trackScrollToView();
    // Array to hold the names of the existing inserts so we can find the latest unassigned slot and current assignments
    var currentInsertButtons = sf.ui.proTools.selectedTrack.invalidate().insertButtons;
    let currentInsertNames = currentInsertButtons.map(getCurrentInsertName);

    let pluginsToMoveCount = currentInsertNames.filter(i => i != 'unassigned').length;

    if (pluginsToMoveCount === 0) return
    let currentlyAssignedSlots = [];

    //I'm sure there's a more elegant way to to do this...
    for (let i = 9; i >= 0; i--) {
        if (currentInsertNames[i] != 'unassigned') currentlyAssignedSlots.push(i);
    }
    //Make sure our two plugin counts agree
    if (pluginsToMoveCount != currentlyAssignedSlots.length) throw "Something's fishy in Denmark";

    //Now remove any that don't have to be moved
    var emptySlotTargetIndex = 0;

    for (let i = pluginsToMoveCount; i >= 0; i--) {
        if (currentlyAssignedSlots[i - 1] != emptySlotTargetIndex) break;

        currentlyAssignedSlots.pop();
        emptySlotTargetIndex++;
    }


    //Now we are left with an array of plugin indexes that need to move and the last free slot 

    if (currentlyAssignedSlots.length === 0) return

    //Set our target index to the last plugin slot
    let pluginMoves = [];
    for (let i = currentlyAssignedSlots.length; i > 0; i--) {
        // log({ s: currentlyAssignedSlots[i-1], d: emptySlotTargetIndex })
        pluginMoves.push({
            sourceIndex: currentlyAssignedSlots[i - 1],
            destIndex: emptySlotTargetIndex
        })

        emptySlotTargetIndex++

    }
    pluginMoves.forEach(m => {
        if (!dragPlugin(m, currentInsertButtons)) throw `Couldn't move an insert after three attemps`;
    });
}
function main() {


    // ---------- Initialise Variables ---------------
    sf.ui.proTools.appActivateMainWindow();
    // Refresh PTs track list
    sf.ui.proTools.mainWindow.invalidate();

    var trackCount = sf.ui.proTools.selectedTrackCount;
    var trackList = sf.ui.proTools.selectedTrackNames;

    // Set up screen

    setupScreen();

    for (var j = 0; j < trackCount; j++) {
        movePlugins(trackList[j])
    }
    sf.ui.proTools.trackSelectByName({names: trackList, deselectOthers: true})
}

main();
// log(sf.ui.proTools.selectedTrack.insertButtons[0].position.x
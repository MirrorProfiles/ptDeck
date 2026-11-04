function dismissDialg() {
    if (sf.ui.proTools.confirmationDialog.invalidate().buttons.whoseTitle.is('Remove').first.exists) {

        sf.ui.proTools.confirmationDialog.buttons.whoseTitle.is('Remove').first.elementClick();

        sf.ui.proTools.confirmationDialog.elementWaitFor({
            waitType: "Disappear",
        });
    }
    if (sf.ui.proTools.confirmationDialog.invalidate().buttons.whoseTitle.is('Change').first.exists) {

        sf.ui.proTools.confirmationDialog.buttons.whoseTitle.is('Change').first.elementClick();

        sf.ui.proTools.confirmationDialog.elementWaitFor({
            waitType: "Disappear",
        });
    }
}


function removeInactive({ inserts = true, sends = true }) {

    if (inserts) {
        //remove inactive inserts
        try {

            for (var i = 0; i < 10; i++) {

                dismissDialg()
                if (sf.ui.proTools.selectedTrack.insertSelectorButtons[i].invalidate().value.value.startsWith("inactive")) {
                    sf.ui.proTools.selectedTrack.trackInsertOrSendSelect({
                        insertOrSend: "Insert",
                        pluginNumber: i + 1,
                        pluginPath: ['no insert']
                    });
                    dismissDialg()
                }
            }
        } catch (err) { }

    }

    if (sends) {
        //remove inactive sends
        try {
            for (var i = 0; i < 10; i++) {

                dismissDialg()
                if (sf.ui.proTools.selectedTrack.sendSelectorButtons[i].invalidate().value.value.startsWith("inactive")) {
                    sf.ui.proTools.selectedTrack.trackInsertOrSendSelect({
                        insertOrSend: "Send",
                        pluginNumber: i + 1,
                        pluginPath: ['no send']
                    });
                    dismissDialg()
                }
            }
        } catch (err) { }
    }
}

function enableMenus(currentValue) {
    sf.ui.proTools.menuClick({
        menuPath: ["View", "Edit Window Views", currentValue],
        targetValue: "Enable"
    });
}


const menus = [
    "Inserts A-E",
    "Inserts F-J",
    "Sends A-E",
    "Sends F-J"
]


/**
 * @param {Object} [arg]
 * @param {boolean} [arg.inserts]
 * @param {boolean} [arg.sends]
 */
function removeInactiveInserts_Sends(arg) {

    //Activate Pro Tools
    sf.ui.proTools.appActivate();
    sf.ui.proTools.invalidate();

    //Enable view of Inserts and Sends
    menus.forEach(enableMenus)

    sf.ui.proTools.invalidate();

    //Get selected tracks
    const originalTracks = sf.ui.proTools.selectedTrackNames;

    //Do for each track.
    sf.ui.proTools.selectedTracks.trackHeaders.slice().map(track => {

        const vcaTrack = track.title.value.endsWith("VCA Track ")
        const basicFolder = track.title.value.endsWith("Basic Folder Track ")
        const midiTrack = track.title.value.endsWith("MIDI Track ")

        if (!vcaTrack && !basicFolder && !midiTrack) {

            //Select track
            track.trackSelect();

            //Scroll track into View
            track.trackScrollToView();

            removeInactive(arg || {})
        }
    });

    //Restore previously selected tracks
    sf.ui.proTools.trackSelectByName({ names: originalTracks });

}


removeInactiveInserts_Sends()


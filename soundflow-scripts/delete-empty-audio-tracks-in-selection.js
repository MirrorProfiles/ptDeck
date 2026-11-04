if (sf.ui.useSfx && !globalState.OPP_disableSfx) sf.ui.useSfx();

if (!sf.ui.proTools.isRunning) throw `Pro Tools is not running`;

if (!sf.ui.proTools.isSfxApplication)
    sf.ui.proTools.appActivateMainWindow();

function processTrack(trackName) {
    sf.ui.proTools.trackSelectByName({ names: [trackName], deselectOthers: true });

    if (sf.ui.proTools.selectedTrack.normalizedTrackName !== trackName)
        throw 'Could not select track: ' + trackName;

    if (sf.ui.proTools.isSfxApplication) {
        sf.ui.proTools.refreshMenuItems();
    } else {
        //Refresh menu
        sf.ui.proTools.selectedTrack.trackScrollToView();
        sf.ui.proTools.selectedTrack.titleButton.mouseClickElement();
    }

    const trackIsEmpty = sf.ui.proTools.getMenuItem('Track', 'Delete').exists;
    const trackIsAudioTrack = sf.ui.proTools.selectedTrack.title.value.indexOf('Audio Track') >= 0;

    if (trackIsEmpty && trackIsAudioTrack) {
        if (sf.ui.proTools.isSfxApplication) {
            sf.ui.proTools.dawCommands.getByUniquePersistedName("DeleteTracks").run({ synchronous: true });
        } else {
            sf.ui.proTools.getMenuItem('Track', 'Delete').elementClick({}, 'Could not delete track: ' + trackName);
        }

        sf.ui.proTools.mainWindow.invalidate();
    }
}

function main() {
    const trackNames = sf.ui.proTools.selectedTrackNames;
    trackNames.forEach(processTrack);
}

main();
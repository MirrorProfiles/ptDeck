// Function to set cab states with Cab 2 on
function setCab2On() {
    // Set Cab 1 to off
    sf.midi.sendCC({
        externalMidiPort: 'Maschine MK3',
        midiChannel: 1,
        midiCC: 104,
        value: 0,
    });

    // Set Cab 2 to on
    sf.midi.sendCC({
        externalMidiPort: 'Maschine MK3',
        midiChannel: 1,
        midiCC: 105,
        value: 127,
    });

    // Set Cab 3 to off
    sf.midi.sendCC({
        externalMidiPort: 'Maschine MK3',
        midiChannel: 1,
        midiCC: 106,
        value: 0,
    });

    // Set Cab 4 to off
    sf.midi.sendCC({
        externalMidiPort: 'Maschine MK3',
        midiChannel: 1,
        midiCC: 107,
        value: 0,
    });
}

// Call the function to set the cab states
setCab2On();
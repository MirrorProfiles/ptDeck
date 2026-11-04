// Function to set all amps and cabs to off
function setAllAmpsAndCabsOff() {
    // Set all amps to off
    sf.midi.sendCC({
        externalMidiPort: 'Maschine MK3',
        midiChannel: 1,
        midiCC: 80,
        value: 0,
    });
    sf.midi.sendCC({
        externalMidiPort: 'Maschine MK3',
        midiChannel: 1,
        midiCC: 81,
        value: 0,
    });
    sf.midi.sendCC({
        externalMidiPort: 'Maschine MK3',
        midiChannel: 1,
        midiCC: 82,
        value: 0,
    });
    sf.midi.sendCC({
        externalMidiPort: 'Maschine MK3',
        midiChannel: 1,
        midiCC: 83,
        value: 0,
    });

    // Set all cabs to off
    sf.midi.sendCC({
        externalMidiPort: 'Maschine MK3',
        midiChannel: 1,
        midiCC: 104,
        value: 0,
    });
    sf.midi.sendCC({
        externalMidiPort: 'Maschine MK3',
        midiChannel: 1,
        midiCC: 105,
        value: 0,
    });
    sf.midi.sendCC({
        externalMidiPort: 'Maschine MK3',
        midiChannel: 1,
        midiCC: 106,
        value: 0,
    });
    sf.midi.sendCC({
        externalMidiPort: 'Maschine MK3',
        midiChannel: 1,
        midiCC: 107,
        value: 0,
    });
}

// Call the function to set all amps and cabs to off
setAllAmpsAndCabsOff();
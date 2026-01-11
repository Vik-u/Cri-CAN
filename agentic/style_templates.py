#!/usr/bin/env python3
import hashlib

TEMPLATES = {
    "broadcast": {
        "wicket": [
            "Gone! {batsman} is out, {bowler} strikes.",
            "Big moment: {bowler} removes {batsman}.",
            "Wicket! {batsman} departs, and {bowler} has the breakthrough.",
        ],
        "boundary": [
            "Cracked away for {runs} - {batsman} times it nicely.",
            "That's {runs}! {batsman} finds the rope off {bowler}.",
            "Clean hit for {runs}, {batsman} cashes in.",
        ],
        "extra": [
            "Extras added there, {bowler} strays a touch.",
            "A bonus run for the batting side.",
            "That one slips down the leg side, extras on offer.",
        ],
        "dot": [
            "Good ball from {bowler}, {batsman} can't score.",
            "Dot ball - {bowler} keeps it tight.",
            "No run, tidy from {bowler}.",
        ],
        "run": [
            "They sneak {runs}, good rotation of strike.",
            "{runs} run(s) there, {batsman} keeps it moving.",
            "Easy {runs}, keeps the scoreboard ticking.",
        ],
    },
    "funny": {
        "wicket": [
            "Oops, that's a ticket out - {batsman} is gone, {bowler} wins it.",
            "That one had trouble written all over it. {batsman} walks.",
            "Send the bails a postcard - {bowler} knocks {batsman} over.",
        ],
        "boundary": [
            "That ball needed a visa - it just flew away for {runs}.",
            "Boundary alert: {batsman} puts {bowler} on the highlight reel for {runs}.",
            "Blink and it's gone. {runs} to {batsman}.",
        ],
        "extra": [
            "Freebies! {bowler} hands out extras like candy.",
            "That's a gift-wrapped run, no receipt needed.",
            "Loose from {bowler}, and the scoreboard smiles.",
        ],
        "dot": [
            "Nothing doing. {bowler} keeps it on a tight leash.",
            "Dot ball - {batsman} left the bat at home for that one.",
            "No run. {bowler} just hit the brakes.",
        ],
        "run": [
            "They jog a {runs} - cardio done.",
            "A casual {runs} and they move along.",
            "Quick {runs}; nice and sneaky.",
        ],
    },
    "serious": {
        "wicket": [
            "Wicket. {batsman} is out, and {bowler} delivers the breakthrough.",
            "A key moment - {bowler} removes {batsman}.",
            "Dismissed. {batsman} has to go.",
        ],
        "boundary": [
            "{runs} runs. {batsman} finds the boundary cleanly.",
            "Controlled stroke for {runs}.",
            "{runs} to {batsman}. That was placed precisely.",
        ],
        "extra": [
            "Extras conceded by {bowler}.",
            "Loose ball, extra runs added.",
            "Unforced extras there.",
        ],
        "dot": [
            "No run. {bowler} maintains control.",
            "Dot ball, good discipline from {bowler}.",
            "Tight line, no scoring.",
        ],
        "run": [
            "{runs} run(s) taken, rotation of strike.",
            "{runs} run(s) and they keep moving.",
            "{runs} run(s), steady accumulation.",
        ],
    },
    "methodical": {
        "wicket": [
            "Wicket recorded: {bowler} dismisses {batsman}.",
            "Event: wicket. {batsman} out to {bowler}.",
            "Outcome: dismissal for {batsman}.",
        ],
        "boundary": [
            "Event: boundary, {runs} runs to {batsman}.",
            "Boundary logged: {runs} off {bowler}.",
            "Scoring event: {runs} runs.",
        ],
        "extra": [
            "Extras recorded: {bowler} concedes.",
            "Extra run(s) added.",
            "Extras taken; no bat contact noted.",
        ],
        "dot": [
            "Dot ball recorded: no run.",
            "No scoring event on this delivery.",
            "Dot ball, good defensive outcome.",
        ],
        "run": [
            "Runs added: {runs}.",
            "Scoring shot yields {runs} run(s).",
            "{runs} run(s) added to total.",
        ],
    },
    "energetic": {
        "wicket": [
            "Boom! {bowler} knocks over {batsman}.",
            "Huge moment - {bowler} sends {batsman} packing!",
            "Wicket! {batsman} gone, and the crowd erupts!",
        ],
        "boundary": [
            "Smashed for {runs}! {batsman} lights it up.",
            "That rockets away for {runs}!",
            "Hammered! {runs} more.",
        ],
        "extra": [
            "Free runs! {bowler} leaks extras.",
            "Bonus on the board - extras given.",
            "Loose delivery, and it costs {bowler}.",
        ],
        "dot": [
            "Locked up tight! {bowler} wins that one.",
            "No run! {bowler} squeezes hard.",
            "Dot ball - pressure builds!",
        ],
        "run": [
            "Quick {runs}, they keep it buzzing.",
            "{runs} on the board, pace stays high.",
            "Snappy {runs} - good hustle.",
        ],
    },
    "roasting": {
        "wicket": [
            "That's a gift, and {bowler} unwraps it - {batsman} gone.",
            "{batsman} tried a shortcut and paid for it. Wicket to {bowler}.",
            "No patience there - {batsman} walks, {bowler} smiles.",
        ],
        "boundary": [
            "{bowler} missed the mark and got punished for {runs}.",
            "That was asking for trouble - {batsman} takes {runs}.",
            "Short, wide, and roasted for {runs}.",
        ],
        "extra": [
            "Free runs again - {bowler} keeps the gifts coming.",
            "That is loose, and the batting side says thanks.",
            "Messy from {bowler}, extras sneak in.",
        ],
        "dot": [
            "Nothing there. {bowler} locks it down.",
            "No run - {batsman} was fishing.",
            "Dot ball. {batsman} stays quiet.",
        ],
        "run": [
            "{runs} run(s) - small wins for {batsman}.",
            "{runs} off it, but nothing flashy.",
            "Just {runs}. Keeps it ticking.",
        ],
    },
}

OVER_TEMPLATES = {
    "broadcast": {
        "open": [
            "Over {over_num}: {runs} runs{wicket_phrase}.",
            "End of over {over_num} - {runs} off it{wicket_phrase}.",
            "{runs} off over {over_num}{wicket_phrase}.",
        ],
        "highlight": [
            "Boundaries from {boundary_batsmen} kept it lively.",
            "The highlight: {boundary_batsmen} {find_verb} the rope.",
            "Key moments from {boundary_batsmen} add the spark.",
        ],
        "close": [
            "Otherwise, mostly singles and dots.",
            "Apart from that, it stays controlled.",
            "A measured over with steady rotation.",
        ],
    },
    "funny": {
        "open": [
            "Over {over_num}: {runs} runs{wicket_phrase}. Not bad for six deliveries.",
            "{runs} off over {over_num}{wicket_phrase}.",
            "Over {over_num} goes for {runs}{wicket_phrase}.",
        ],
        "highlight": [
            "Boundaries from {boundary_batsmen} did the heavy lifting.",
            "{boundary_batsmen} did the loud work with the big hits.",
            "The rope got a workout thanks to {boundary_batsmen}.",
        ],
        "close": [
            "Otherwise, it's a jog-and-nod kind of over.",
            "The rest is just singles and polite applause.",
            "Not many fireworks outside the boundaries.",
        ],
    },
    "serious": {
        "open": [
            "Over {over_num}: {runs} runs{wicket_phrase}.",
            "{runs} from that over{wicket_phrase}.",
            "Over {over_num} yields {runs}{wicket_phrase}.",
        ],
        "highlight": [
            "Boundaries from {boundary_batsmen} were decisive.",
            "{boundary_batsmen} provide the key scoring strokes.",
            "The scoring surge comes via {boundary_batsmen}.",
        ],
        "close": [
            "Otherwise, steady accumulation.",
            "The remainder is controlled rotation.",
            "Minimal risk outside the scoring shots.",
        ],
    },
    "methodical": {
        "open": [
            "Over {over_num} summary: {runs} runs{wicket_phrase}.",
            "Over {over_num} totals {runs}{wicket_phrase}.",
            "Over {over_num}: {runs} recorded{wicket_phrase}.",
        ],
        "highlight": [
            "Boundary events: {boundary_batsmen}.",
            "Primary scoring via {boundary_batsmen}.",
            "Notable boundaries from {boundary_batsmen}.",
        ],
        "close": [
            "Other deliveries yield low scoring.",
            "Remaining balls produce singles or dots.",
            "Non-boundary deliveries are contained.",
        ],
    },
    "energetic": {
        "open": [
            "Over {over_num}: {runs} runs{wicket_phrase}!",
            "{runs} off over {over_num}{wicket_phrase} - pace stays high!",
            "Over {over_num} goes for {runs}{wicket_phrase}!",
        ],
        "highlight": [
            "{boundary_batsmen} bring the fireworks with the boundaries.",
            "Boundaries from {boundary_batsmen} light it up.",
            "{boundary_batsmen} put the crowd on its feet.",
        ],
        "close": [
            "The rest is hustle and pressure.",
            "Still plenty of energy in that over.",
            "Not a dull ball in that spell.",
        ],
    },
    "roasting": {
        "open": [
            "Over {over_num}: {runs} runs{wicket_phrase}. Could have been tighter.",
            "{runs} off over {over_num}{wicket_phrase}. Not exactly stingy.",
            "Over {over_num} goes for {runs}{wicket_phrase}.",
        ],
        "highlight": [
            "{boundary_batsmen} made sure the bowler paid.",
            "Boundaries from {boundary_batsmen} did the damage.",
            "{boundary_batsmen} cashed in on the mistakes.",
        ],
        "close": [
            "Other balls are just damage control.",
            "The rest is singles and a bit of survival.",
            "Not a great over outside the big shots.",
        ],
    },
}


def pick_template(style, event_type, seed_key):
    style_templates = TEMPLATES.get(style, TEMPLATES["broadcast"])
    options = style_templates.get(event_type, style_templates["run"])
    h = hashlib.md5(seed_key.encode("utf-8")).hexdigest()
    idx = int(h, 16) % len(options)
    return options[idx]


def pick_over_template(style, key, seed_key):
    style_templates = OVER_TEMPLATES.get(style, OVER_TEMPLATES["broadcast"])
    options = style_templates.get(key, style_templates["open"])
    h = hashlib.md5(seed_key.encode("utf-8")).hexdigest()
    idx = int(h, 16) % len(options)
    return options[idx]


def render_style(style, event_type, bowler, batsman, runs, seed_key):
    template = pick_template(style, event_type, seed_key)
    batsman_last = (batsman or "").split()[-1] if batsman else ""
    bowler_last = (bowler or "").split()[-1] if bowler else ""
    return template.format(
        bowler=bowler,
        batsman=batsman,
        bowler_last=bowler_last,
        batsman_last=batsman_last,
        runs=runs,
    )


def render_over(style, summary, seed_key):
    boundary_batsmen = summary.get("boundary_batsmen") or "the batters"
    wicket_phrase = summary.get("wicket_phrase") or ""
    over_num = summary.get("over_num")
    runs = summary.get("runs")
    is_plural = " and " in boundary_batsmen or "," in boundary_batsmen
    find_verb = "find" if is_plural else "finds"

    open_line = pick_over_template(style, "open", seed_key).format(
        over_num=over_num,
        runs=runs,
        wicket_phrase=wicket_phrase,
    )

    lines = [open_line]

    if summary.get("boundary_batsmen_list"):
        highlight = pick_over_template(style, "highlight", seed_key + "|h").format(
            boundary_batsmen=boundary_batsmen,
            find_verb=find_verb,
        )
        lines.append(highlight)

    close_line = pick_over_template(style, "close", seed_key + "|c").format(
        boundary_batsmen=boundary_batsmen,
        find_verb=find_verb,
    )
    lines.append(close_line)

    return " ".join(line.strip() for line in lines if line.strip())

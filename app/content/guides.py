"""Original, public editorial content. Never source these pages from user uploads."""
GUIDES = {
    'basketball-shooting-form-check': {
        'title': 'Basketball Shooting Form Check: A Video Review Checklist',
        'description': 'Check your basketball shooting form with a repeatable video checklist: camera angle, shot sequence, visible measurements, and one focus for your next practice.',
        'summary': 'A form check is most useful when you can point to a moment in the video and describe what you see. Start with one question, then compare like-for-like clips.',
        'sections': [
            ('Start with a question you can observe', [
                '“Is my shooting form good?” is difficult to answer from a single attempt. A more useful question is whether the ball pauses as it rises, where your hand is when the ball leaves it, or whether your landing changes between attempts. Write down the situation too: stationary shot, catch and shoot, or a shot off the dribble.',
                'A made basket does not prove that every part of the motion is repeatable. A miss does not identify a specific mechanical fault. Keep the outcome alongside the clip as context, rather than treating it as the explanation.'
            ]),
            ('Review the whole sequence before judging one frame', [
                'Play the clip at normal speed first. Then review the start of the motion, the ball dip if one is visible, the upward movement, the estimated release, and the follow-through. A still image can help locate a position; the frames around it tell you how the player arrived there.',
                'Use the same event when comparing attempts. The lowest ball position and the deepest knee bend may occur at different times. Matching two timestamps is not enough if the clips start at different points in the action.'
            ]),
            ('A practical form-check checklist', [
                'Can you see the entire shooting arm, hips, knees and feet? Is the camera steady? Is the ball still visible above the head? If a joint is hidden or the hand leaves the frame, mark that observation as uncertain instead of filling in the gap.',
                'Look at one movement at a time: the ball’s path, the order of the visible body movements, or the position at release. Record an observation such as “the ball stops briefly near the forehead,” followed by a question such as “does this happen in the other clips?” This keeps observation separate from advice.',
                'Film several comparable attempts separately. Keep distance, camera position and shot type similar. Changing all three makes it hard to know whether a difference belongs to your movement or to the recording.'
            ]),
            ('Use the analyzer as a review aid', [
                'FormRefine extracts candidate keyframes and estimates visible joint angles from a short video. You can review those moments against the original clip. A camera-based angle is a measurement of the recorded view, not a direct measurement of joint force, power, or shooting potential.',
                'Choose one observation to discuss or practice, then record another clip under similar conditions and compare your saved analyses. General shooting instruction and a coach’s judgment remain useful alongside the measurements.'
            ]),
        ],
        'faqs': [('Can a form checker tell me why I missed?', 'It can help locate visible movement patterns, but a single video cannot establish the cause of a miss or predict your future shooting percentage.'), ('Do I need to copy an NBA player’s form?', 'A reference can illustrate a movement. It is not a universal target for every body or shot situation. Comparing your own clips from similar conditions is often easier to interpret.')],
        'sources': [('Jr. NBA: How to Shoot a Basketball', 'https://jr.nba.com/shooting/')],
        'related': ['how-to-film-basketball-shot', 'basketball-shooting-dip'],
    },
    'how-to-film-basketball-shot': {
        'title': 'How to Film Your Basketball Shot for Form Analysis',
        'description': 'Record a clear basketball shooting video for form analysis: a steady side view, full-body framing, one complete shot, and consistent follow-up conditions.',
        'summary': 'A useful shooting video starts before the ball rises and ends after the follow-through. Give the reviewer enough room to see both your feet and the ball.',
        'sections': [
            ('Set the camera before you shoot', [
                'Start with a side view where the shooting arm is visible. Put the phone on a stable support, level with the court rather than pointing steeply up or down. Keep the camera stationary throughout the attempt. A friend can check the framing while you rehearse the motion.',
                'Leave space above the raised hand and below the feet. Step through the complete shot once without recording: the ball, arm and landing should stay inside the picture. If you move forward on the shot, leave room in that direction too.'
            ]),
            ('Choose the view for the question', [
                'A side view makes it easier to review upward movement and the sequence of knee, hip and arm motion. A front view can provide a different view of alignment, but may hide the shooting elbow behind the ball. Do not compare angle numbers from those two views as though they were the same measurement.',
                'Record additional views as separate clips when you need them. Avoid walking around the shooter during a recording: moving the camera changes the apparent geometry and makes comparisons less useful.'
            ]),
            ('Capture one complete attempt', [
                'Begin before the player lowers or gathers the ball. Keep filming until the player has landed and finished the follow-through. If the clip starts halfway through the dip, the true low point may be outside the recording.',
                'Use a well-lit court, keep other players out of the foreground, and avoid heavy digital zoom. Keep the original video when possible. Screen recordings, repeated social-media compression and motion blur can make the hand and ball harder to separate.',
                'The web uploader accepts MP4, MOV, AVI and WebM. Keep each clip within the size and duration limits shown beside the upload control. If a long recording contains many shots, trim out one complete attempt rather than cutting only the instant of release.'
            ]),
            ('Make a follow-up comparable', [
                'Note the camera position, shooting distance, shot type and shooting hand. Repeat those conditions for the follow-up. Also record whether you practiced the intended adjustment and how it felt; the video alone cannot tell us what you were trying to do.',
                'If the conditions changed, say so. A moving catch-and-shoot attempt and a stationary practice attempt can both be useful clips, but they answer different questions. Keep makes and misses as additional notes rather than using one result to declare an improvement.'
            ]),
        ],
        'faqs': [('Do I need a professional camera?', 'No. A phone video can be useful when the body stays visible, the camera is steady, and the movement is clear.'), ('Why did the analyzer miss a keyframe?', 'The event may be outside the clip, hidden by another person or the ball, blurred, or difficult for pose estimation to identify. Check the original video before accepting an automatic timestamp.')],
        'sources': [],
        'related': ['basketball-shooting-form-check', 'basketball-release-point'],
    },
    'basketball-shooting-dip': {
        'title': 'Basketball Shooting Dip: How to Review the Low Point',
        'description': 'Understand the shooting dip, distinguish the ball’s low point from knee bend, and review the dip in a basketball video without treating one frame as a diagnosis.',
        'summary': 'The shooting dip is the downward movement of the ball before it rises into the shot. The dip point is the transition near its lowest position, not automatically the deepest squat.',
        'sections': [
            ('Ball dip, knee bend and hip bend are different observations', [
                'The ball can reach its lowest position before or after the legs reach their deepest bend. A low ball position does not by itself show excessive knee bend or hip bend. Review the ball, knees and trunk separately, then look at their sequence in the video.',
                'Camera angle also matters. Leaning toward or away from the camera changes the apparent body position. A single still image does not measure how effectively a player generates force or whether that movement limits shooting range.'
            ]),
            ('Find the dip in the clip', [
                'Locate the upward ball movement that leads into the shot. Move backward through nearby frames and look for the transition from lowering to lifting. Check the surrounding motion so that a preceding dribble is not mistaken for the shooting dip.',
                'If the clip begins with the ball already rising, its lowest visible position might be the first frame. That does not confirm that the true low point happened in the recording. Label the start as incomplete and record an earlier lead-in next time.',
                'FormRefine uses pose-based signals to estimate key moments. The visible hand position is not the same as a direct measurement of the ball’s center. Treat the suggested timestamp as a place to review, especially when the ball hides the hand or the shooter changes direction.'
            ]),
            ('Should you remove the dip?', [
                'There is no basis for deciding from the presence of a dip alone. A published experiment with high-school and university players found better shooting accuracy with a dip under its tested conditions. That result does not establish the best dip depth for you or settle every game-speed catch-and-shoot situation.',
                'Describe the actual question: are you investigating an extra downward motion after a high catch, a pause before lifting, or a different rhythm after a dribble? Those are more specific than asking whether every dip is good or bad.'
            ]),
            ('Compare one change at a time', [
                'Record comparable attempts from the same distance and camera position. Review the ball path and the time sequence, then note how the movement felt. If you experiment with a different dip, keep the other recording conditions similar and avoid judging the change from a single make.',
                'A useful review note might be: “The ball drops after the catch in these two clips; I want to compare the rhythm with the next recording.” A claim that the dip is wasting power would require more evidence than those frames provide.'
            ]),
        ],
        'faqs': [('Is the dip point the lowest knee position?', 'No. The ball’s change of direction and the deepest knee bend are distinct events and can occur at different times.'), ('Can the first frame be the dip point?', 'It can be the lowest visible position, but if the lowering phase was cut off, the recording does not establish the true dip point.')],
        'sources': [('Penner (2021): Mechanics of the Jump Shot — The “Dip” Increases the Accuracy of Elite Basketball Shooters', 'https://pmc.ncbi.nlm.nih.gov/articles/PMC8273237/')],
        'related': ['basketball-shooting-form-check', 'basketball-release-point'],
    },
    'basketball-release-point': {
        'title': 'Basketball Release Point: Find and Compare It on Video',
        'description': 'Find the basketball release point in a shooting video, distinguish release from wrist peak, and compare attempts without confusing arm angle with ball launch angle.',
        'summary': 'Release is the moment the ball leaves the shooting hand. The hand’s highest position can occur later, so the highest wrist frame is not a substitute for the release frame.',
        'sections': [
            ('Locate separation, not just full arm extension', [
                'Find the last frame with clear hand-ball contact and the first frame with clear separation. The release occurred between them. If the ball is blurred or hidden, keep that uncertainty in the observation instead of choosing an exact instant with confidence.',
                'Arm extension and wrist motion are useful context, but they do not prove that the ball has already left the hand. Continue a few frames forward to distinguish the release from the later follow-through or wrist peak.'
            ]),
            ('Understand the timing limit', [
                'Video samples motion in individual frames. At 30 frames per second, neighboring frames are about 0.033 seconds apart. An event between those frames cannot be timed more precisely by simply displaying additional decimal places.',
                'Slow-motion playback helps you inspect the frames that exist. It does not create missing evidence. If the recording was exported with a changed playback speed, check whether its timestamps still represent the original shooting time before comparing durations.'
            ]),
            ('Compare the same event and camera view', [
                'For each clip, identify release independently, then compare what is visible at that event. Use the same side view, camera height and shooting situation. A hand that appears higher in the image may reflect framing or perspective rather than a higher release relative to the player.',
                'Keep release position, release timing and ball launch angle separate. An elbow angle describes the visible arm configuration. A ball launch angle describes the initial path of the ball. FormRefine’s pose measurements should not be presented as a measured ball trajectory.'
            ]),
            ('Turn the comparison into a useful question', [
                'First describe a repeated observation, such as the hand releasing near a similar position across comparable attempts. Then decide what to investigate with your next recording. One unusual frame could be a different shot, an occlusion, or a detection error.',
                'FormRefine displays an estimated release candidate so you can inspect the original action. If the hand is hidden, retake the clip with a clearer side view. Use human review when you need help interpreting the movement rather than assuming that a particular angle is correct for everyone.'
            ]),
        ],
        'faqs': [('Is the release point the highest point of the jump?', 'These are different events. Locate the ball leaving the hand rather than assuming release occurs at the top of the jump.'), ('Can an elbow angle tell me the ball’s launch angle?', 'No. They measure different things. Estimating ball launch angle requires observing the ball’s motion, not just the arm pose.')],
        'sources': [],
        'related': ['how-to-film-basketball-shot', 'basketball-shooting-dip'],
    },
}

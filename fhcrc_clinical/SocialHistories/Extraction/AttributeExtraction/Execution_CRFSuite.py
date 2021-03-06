import traceback

import nltk
import pycrfsuite

from DataModeling.DataModels import Attribute
from Extraction.AttributeExtraction.Processing_CRFSuite import sent2features, tokenize_sentences, standardize_tokens, \
    standardize_tokens_list
from SystemUtilities.Configuration import ATTRIB_EXTRACTION_DIR_HOME
from SystemUtilities.Globals import entity_types
from SystemUtilities.Parameter_Configuration import SENTENCE_TOK_PATTERN
import os

def extract(patients, model_path=ATTRIB_EXTRACTION_DIR_HOME):
    # Extract all sentences with subs info + the sentence after
    all_sentences = get_sentences_with_info_plus_sentence_after(patients)

    for type in entity_types: # {Amount, Duration, QuiteDate, TimeAgo, QuitAge, SecondhandAmount}
        model_name = os.path.join(model_path, "model-" + type + ".ser.gzwl")
        test(all_sentences, model_name, type)
    print("Finished CRF classification")


def test(test_sents, model_name, type):
    print "Pulling out " + type + " information ..."
    tagger = pycrfsuite.Tagger()
    print "\tOpening model at: " + model_name
    tagger.open(model_name)
    tagged_sents = list()

    #do tokenization/preprocessing on sentences
    toked_test_sents, obsolete_label_ignore = tokenize_sentences(test_sents)

    for i in range(0, len(toked_test_sents), 1):
        tokd_sent=toked_test_sents[i]
        sent_obj = test_sents[i]
        # Tag for POS
        tagged_sent = nltk.pos_tag(tokd_sent)
        tagged_sents.append(tagged_sent)
        # Recover spans
        tokenized_text, spans = recover_spans(sent_obj.text)
        # Standardize dates, nums, amounts
        tokenized_text = standardize_tokens(tokenized_text)
        # combine standardized and pos-tagged token for input into vectorizer
        vectorizer_input = combine_tokens(tokenized_text, tagged_sent)
        # Generate feature vectors
        feature_vectors = sent2features(vectorizer_input)
        # Predict type sequence
        predictions = tagger.tag(feature_vectors)
        probability = tagger.probability(predictions)

        classified_text = zip(tokenized_text, predictions)

        # Expand tuple to have span as well as probability
        final_class_and_span = list()
        for idx, tup in enumerate(classified_text):
            combined = (classified_text[idx][0], classified_text[idx][1], spans[idx][0], spans[idx][1], probability)
            final_class_and_span.append(combined)
        # Set prediction in sentence object
        sent_obj.sentence_attribs.extend(get_attributes(final_class_and_span))


def recover_spans(text):
    tokenized_text = list()
    spans = list()
    for match in nltk.re.finditer(SENTENCE_TOK_PATTERN, text):
        start = match.start()
        end = match.end()
        word = match.group(0)
        tokenized_text.append(word)
        spans.append((start, end))
    return tokenized_text, spans


def get_sentences_with_info_plus_sentence_after(patients):
    all_sents = list()
    for patient in patients:
        for document in patient.doc_list:
            grab_next = False
            for sentence in document.sent_list:
                if len(sentence.predicted_events) > 0 or grab_next:
                    if grab_next:
                        grab_next = False
                    if len(sentence.predicted_events) > 0:
                        grab_next = True
                    all_sents.append(sentence)
    return all_sents


def get_attributes(crf_classification_tuple_list):
    attribs = list()
    i = 0
    while i < len(crf_classification_tuple_list):
        crf_classification_tuple = crf_classification_tuple_list[i]
        classL = crf_classification_tuple[1]
        start = crf_classification_tuple[2]
        if classL != "0": # beginning of a labeled span
            full_begin_span = start
            full_end_span = start
            full_text = ""
            while i < len(crf_classification_tuple_list) and classL == crf_classification_tuple_list[i][1]:
                crf_classification_tuple = crf_classification_tuple_list[i]
                full_text += crf_classification_tuple[0] + " "
                full_end_span = crf_classification_tuple[3]
                i += 1
            attrib = Attribute(classL, full_begin_span, full_end_span, full_text, probability=crf_classification_tuple[4])
            attribs.append(attrib)
        i += 1
    return attribs


def combine_tokens(standardized_toks, tagged_toks):
    assert (len(standardized_toks) == len(tagged_toks))
    new_token_tuples = list()
    for i in range(len(standardized_toks)):
        new_tuple = (standardized_toks[i], tagged_toks[i][1])
        new_token_tuples.append(new_tuple)
    return new_token_tuples


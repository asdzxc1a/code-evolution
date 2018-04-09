import { createStore, compose } from 'redux';
import rootReducers from './reducers';

const state = {
 columns: [{
    title: '',
    cards: [],
  }],
  cards: [],
  card: {},
}

export default createStore(rootReducers, state, compose(
  typeof window === 'object'
  && typeof window.devToolsExtension !== 'undefined'
    ? window.devToolsExtension()
    : (feed) => feed,
));
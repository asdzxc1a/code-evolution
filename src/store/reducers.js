
import * as consts from './actionConsts';

const initialState = {
 columns: [{
    title: '',
    cards: [],
  }],
  cards: [],
  card: {},
}


export default (state = initialState, actions) => {
  let newState = {};
  let columns = [].concat(state.columns);
  switch (actions.type) {
    case consts.ADD_COLUMN:
      columns = [].concat(state.columns);
      columns[columns.length - 1] = {
        title: actions.columnName,
        cards: [],
      };
      columns.push({
        title: '',
        cards: [],
      });
      newState = { columns };
      break;

    case consts.ADD_CARD:
      columns[actions.columnIndex].cards.push({
        createdAt: Date.now(),
        description: actions.description,
      });
      newState = { columns };
      break;

    case consts.SHIFT_CARD:
      const { srcColumnIndex, targetColumnIndex, srcCardIndex } = actions;
      if (srcColumnIndex !== targetColumnIndex) {
        const card = Object.assign({}, columns[srcColumnIndex].cards[srcCardIndex]);
        columns[srcColumnIndex].cards.splice(srcCardIndex, 1);
        columns[targetColumnIndex].cards.push(card);
        newState = { columns };
      }
      break;

    case consts.REMOVE_CARD:
      columns[actions.columnIndex].cards.splice(actions.cardIndex, 1);
      newState = { columns };
      break;

    case consts.REMOVE_COLUMN:
      columns.splice(actions.columnIndex, 1);
      newState = { columns };
      break;
    case consts.SWAP_CARD:
      const { src, target } = actions;
      const tempCardStore = columns[src.columnIndex].cards[src.cardIndex];
      columns[src.columnIndex].cards[src.cardIndex] = columns[target.columnIndex].cards[target.cardIndex];
      columns[target.columnIndex].cards[target.cardIndex] = tempCardStore;
      newState = { columns };
      break;
    default:
      newState = state;
      break;
  }
  return Object.assign({}, state, newState);
}